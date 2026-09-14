import io
import os
import pandas as pd
import psycopg2
from sshtunnel import SSHTunnelForwarder
import streamlit as st
import paramiko

st.set_page_config(
    page_title="Informes Contables Odoo", page_icon="📊", layout="centered"
)
st.title("📊 Exportador de Apuntes Contables")


def load_ssh_key(key_string):
    """Prueba automáticamente los tipos de clave SSH válidos."""
    for key_class in (
        paramiko.Ed25519Key,
        paramiko.RSAKey,
        paramiko.ECDSAKey,
        paramiko.DSSKey,
    ):
        try:
            return key_class.from_private_key(io.StringIO(key_string))
        except Exception:
            pass
    raise ValueError(
        "No se pudo parsear la clave SSH. Verifica el formato en Streamlit Secrets."
    )


password = st.text_input("Contraseña de acceso:", type="password")

if password == os.getenv("APP_PASSWORD"):
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Fecha Inicio")
    with col2:
        end_date = st.date_input("Fecha Fin")

    if st.button("Generar Informe", type="primary"):
        if start_date > end_date:
            st.error("La fecha de inicio no puede ser posterior a la fecha fin.")
        else:
            with st.spinner("Conectando por túnel SSH a Odoo.sh..."):
                tunnel = None
                conn = None
                try:
                    ssh_host = os.getenv("SSH_HOST", "upgyms-iberia-sh.odoo.com")
                    ssh_user = os.getenv("SSH_USER", "4984370")

                    # Carga dinámica probando todos los formatos válidos
                    ssh_key_string = os.getenv("SSH_PRIVATE_KEY")
                    pkey = load_ssh_key(ssh_key_string)

                    db_name = os.getenv("DB_NAME")
                    db_user = os.getenv("DB_USER")
                    db_pass = os.getenv("DB_PASS")

                    tunnel = SSHTunnelForwarder(
                        (ssh_host, 22),
                        ssh_username=ssh_user,
                        ssh_pkey=pkey,
                        remote_bind_address=("127.0.0.1", 5432),
                    )
                    tunnel.start()

                    conn = psycopg2.connect(
                        host="127.0.0.1",
                        port=tunnel.local_bind_port,
                        database=db_name,
                        user=db_user,
                        password=db_pass,
                        sslmode="disable",
                        connect_timeout=10,
                    )

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

                    df = pd.read_sql_query(query, conn, params=(start_date, end_date))

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
                    if conn:
                        conn.close()
                    if tunnel:
                        tunnel.stop()

elif password != "":
    st.error("Contraseña incorrecta.")
