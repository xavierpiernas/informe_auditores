import io
import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

st.set_page_config(
    page_title="Informes Contables Odoo", page_icon="📊", layout="centered"
)
st.title("📊 Exportador de Apuntes Contables")


def get_secret(key, default=""):
    """Busca primero en variables de entorno y luego en Streamlit Secrets."""
    if key in os.environ:
        return os.environ[key]
    if hasattr(st, "secrets") and key in st.secrets:
        return st.secrets[key]
    return default


# Autenticación simple
password = st.text_input("Contraseña de acceso:", type="password")
app_password = get_secret("APP_PASSWORD")

if password and password == app_password:
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Fecha Inicio")
    with col2:
        end_date = st.date_input("Fecha Fin")

    if st.button("Generar Informe", type="primary"):
        if start_date > end_date:
            st.error("La fecha de inicio no puede ser posterior a la fecha fin.")
        else:
            with st.spinner("Extrayendo datos de Odoo..."):
                engine = None
                try:
                    db_user = get_secret("DB_USER")
                    db_pass = get_secret("DB_PASS")
                    db_host = get_secret("DB_HOST")
                    db_port = get_secret("DB_PORT", "5432")
                    db_name = get_secret("DB_NAME")
                    ssl_mode = get_secret("DB_SSLMODE", "require")

                    # URL de conexión con SQLAlchemy para PostgreSQL
                    db_url = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?sslmode={ssl_mode}"
                    
                    engine = create_engine(db_url, connect_args={"connect_timeout": 10})

                    query = """
                    SELECT 
                        aml.date AS fecha,
                        aml.name AS etiqueta,
                        am.name AS asiento,
                        aa.code AS cuenta,
                        aml.date_maturity AS fecha_vencimiento,
                        aml.debit AS debe,
                        aml.credit AS haber,
                        aml.amount_currency AS importe_moneda,
                        aml.balance AS saldo,
                        aml.create_date AS fecha_creacion,
                        rp.name AS usuario_creacion
                    FROM account_move_line aml
                    JOIN account_account aa ON aml.account_id = aa.id
                    JOIN account_move am ON aml.move_id = am.id
                    LEFT JOIN res_users ru ON aml.create_uid = ru.id
                    LEFT JOIN res_partner rp ON ru.partner_id = rp.id
                    WHERE aml.parent_state = 'posted'
                    AND aml.date BETWEEN %s AND %s
                    ORDER BY aml.date ASC
                    """

                    # Carga mediante SQLAlchemy Engine
                    df = pd.read_sql_query(query, engine, params=(start_date, end_date))

                    if df.empty:
                        st.warning(
                            "No se encontraron apuntes contables en ese rango de fechas."
                        )
                    else:
                        csv_buffer = io.StringIO()
                        df.to_csv(csv_buffer, index=False, sep="|")
                        csv_bytes = csv_buffer.getvalue().encode("utf-8")

                        st.success(
                            f"¡Informe generado con éxito! Total registros: **{len(df):,}**"
                        )

                        st.download_button(
                            label="⬇️ Descargar CSV para Auditores",
                            data=csv_bytes,
                            file_name=f"apuntes_contables_{start_date}_{end_date}.csv",
                            mime="text/csv",
                        )

                except Exception as e:
                    st.error(f"Error de conexión o consulta: {e}")
                finally:
                    if engine:
                        engine.dispose()

elif password != "":
    st.error("Contraseña incorrecta.")
