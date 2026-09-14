import io
import os
import time
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
            try:
                url = os.getenv(
                    "ODOO_URL",
                    "https://upgyms-iberia-sh.odoo.com",
                )
                db = os.getenv("DB_NAME")
                username = os.getenv("ODOO_USER")
                pwd = os.getenv("ODOO_PASS")

                with st.spinner("Autenticando en Odoo..."):
                    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
                    uid = common.authenticate(db, username, pwd, {})

                if not uid:
                    st.error("Error: Credenciales de Odoo incorrectas.")
                else:
                    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

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

                    # 1. Obtener total de registros
                    with st.spinner("Contando registros a descargar..."):
                        total_count = models.execute_kw(
                            db, uid, pwd, "account.move.line", "search_count", [domain]
                        )

                    if total_count == 0:
                        st.warning("No se encontraron apuntes contables en ese rango.")
                    else:
                        st.info(f"Registros totales a procesar: **{total_count:,}**")

                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        all_records = []
                        limit = 2000  # Subimos lote para más velocidad
                        offset = 0

                        # Inicio del cronómetro
                        start_time = time.time()

                        # 2. Bucle de descarga con cálculo de tiempo restante
                        while offset < total_count:
                            batch = models.execute_kw(
                                db,
                                uid,
                                pwd,
                                "account.move.line",
                                "search_read",
                                [domain],
                                {
                                    "fields": fields,
                                    "order": "date asc",
                                    "limit": limit,
                                    "offset": offset,
                                },
                            )

                            if not batch:
                                break

                            all_records.extend(batch)
                            offset += limit

                            # Métrica de tiempo y velocidad
                            elapsed_time = time.time() - start_time
                            downloaded_count = len(all_records)
                            records_per_sec = downloaded_count / elapsed_time if elapsed_time > 0 else 0

                            # Estimación por regla de tres de lo que falta
                            remaining_records = total_count - downloaded_count
                            remaining_seconds = remaining_records / records_per_sec if records_per_sec > 0 else 0

                            # Formato legible (Minutos y Segundos)
                            mins, secs = divmod(int(remaining_seconds), 60)
                            time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

                            # Feedback dinámico
                            status_text.markdown(
                                f"⏳ **Descargando:** `{downloaded_count:,}` / `{total_count:,}` registros "
                                f"| ⚡ `{records_per_sec:.0f} reg/s` "
                                f"| ⏱️ **Tiempo restante:** ~`{time_str}`"
                            )

                            prog_val = min(1.0, downloaded_count / total_count)
                            progress_bar.progress(prog_val)

                        status_text.text("⚙️ Generando archivo CSV...")

                        # 3. Mapeo final
                        data = []
                        for r in all_records:
                            data.append(
                                {
                                    "fecha": r.get("date"),
                                    "etiqueta": r.get("name"),
                                    "asiento": r["move_id"][1] if r.get("move_id") else "",
                                    "cuenta": r["account_id"][1].split(" ")[0] if r.get("account_id") else "",
                                    "fecha_vencimiento": r.get("date_maturity"),
                                    "debe": r.get("debit"),
                                    "haber": r.get("credit"),
                                    "importe_moneda": r.get("amount_currency"),
                                    "saldo": r.get("balance"),
                                    "fecha_creacion": r.get("create_date"),
                                    "usuario_creacion": r["create_uid"][1] if r.get("create_uid") else "",
                                }
                            )

                        df = pd.DataFrame(data)

                        csv_buffer = io.StringIO()
                        df.to_csv(csv_buffer, index=False, sep="|")
                        csv_bytes = csv_buffer.getvalue().encode("utf-8")

                        status_text.empty()
                        progress_bar.empty()

                        total_duration = int(time.time() - start_time)
                        tot_mins, tot_secs = divmod(total_duration, 60)

                        st.success(
                            f"¡Completado en **{tot_mins}m {tot_secs}s**! Total: **{len(df):,}** registros."
                        )

                        st.download_button(
                            label="⬇️ Descargar CSV para Auditores",
                            data=csv_bytes,
                            file_name=f"apuntes_contables_{start_date}_{end_date}.csv",
                            mime="text/csv",
                        )

            except Exception as e:
                st.error(f"Error de conexión: {e}")

elif password != "":
    st.error("Contraseña incorrecta.")
