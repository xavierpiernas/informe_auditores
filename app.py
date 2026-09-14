import io
import os
import xmlrpc.client
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Informes Contables Odoo", page_icon="📊", layout="centered"
)
st.title("📊 Exportador de Apuntes Contables")

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
            with st.spinner("Extrayendo datos de Odoo..."):
                try:
                    url = os.getenv(
                        "ODOO_URL",
                        "https://upgyms-iberia-sh.odoo.com",
                    )
                    db = os.getenv("DB_NAME")
                    username = os.getenv("ODOO_USER")
                    pwd = os.getenv("ODOO_PASS")

                    # Conexión limpia mediante API HTTPS
                    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
                    uid = common.authenticate(db, username, pwd, {})

                    if not uid:
                        st.error("Error: Credenciales de Odoo incorrectas.")
                    else:
                        models = xmlrpc.client.ServerProxy(
                            f"{url}/xmlrpc/2/object"
                        )

                        domain = [
                            ("parent_state", "=", "posted"),
                            ("date", ">=", str(start_date)),
                            ("date", "<=", str(end_date)),
                        ]

                        fields = [
                            "date",
                            "name",
                            "move_id",
                            "account_id",
                            "date_maturity",
                            "debit",
                            "credit",
                            "amount_currency",
                            "balance",
                            "create_date",
                            "create_uid",
                        ]

                        records = models.execute_kw(
                            db,
                            uid,
                            pwd,
                            "account.move.line",
                            "search_read",
                            [domain],
                            {"fields": fields, "order": "date asc"},
                        )

                        if not records:
                            st.warning("No se encontraron apuntes contables.")
                        else:
                            data = []
                            for r in records:
                                data.append(
                                    {
                                        "fecha": r.get("date"),
                                        "etiqueta": r.get("name"),
                                        "asiento": r["move_id"][1]
                                        if r.get("move_id")
                                        else "",
                                        "cuenta": r["account_id"][1].split(" ")[
                                            0
                                        ]
                                        if r.get("account_id")
                                        else "",
                                        "fecha_vencimiento": r.get(
                                            "date_maturity"
                                        ),
                                        "debe": r.get("debit"),
                                        "haber": r.get("credit"),
                                        "importe_moneda": r.get(
                                            "amount_currency"
                                        ),
                                        "saldo": r.get("balance"),
                                        "fecha_creacion": r.get("create_date"),
                                        "usuario_creacion": r["create_uid"][1]
                                        if r.get("create_uid")
                                        else "",
                                    }
                                )

                            df = pd.DataFrame(data)

                            csv_buffer = io.StringIO()
                            df.to_csv(csv_buffer, index=False, sep="|")
                            csv_bytes = csv_buffer.getvalue().encode("utf-8")

                            st.success(
                                f"¡Informe generado! Registros: **{len(df):,}**"
                            )

                            st.download_button(
                                label="⬇️ Descargar CSV",
                                data=csv_bytes,
                                file_name=f"apuntes_contables_{start_date}_{end_date}.csv",
                                mime="text/csv",
                            )

                except Exception as e:
                    st.error(f"Error: {e}")

elif password != "":
    st.error("Contraseña incorrecta.")
