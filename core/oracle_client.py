# core/oracle_client.py

import os

import oracledb


# ============================================================

# THICK MODE INITIALIZATION (REQUIRED - DB enforces encryption)

# ============================================================

def _init_thick_mode():

    """

    Initialize Oracle Client in thick mode.

    Required because the DB enforces Native Network Encryption.

    """

    if getattr(_init_thick_mode, "_initialized", False):

        return

    oracle_home = r"C:\Oracle64\19cClient\bin"

    tns_admin = r"C:\Oracle64\19cClient\network\admin"

    # Ensure Django/admin always has proper network config

    os.environ["TNS_ADMIN"] = tns_admin

    oracledb.init_oracle_client(lib_dir=oracle_home)

    _init_thick_mode._initialized = True


# ============================================================

# CONNECTION FACTORY

# ============================================================

def get_connection():

    """

    Create Oracle connection in thick mode.

    Required env vars:

        ORACLE_USER

        ORACLE_PASSWORD

        ORACLE_DSN  (e.g. "IBISEAP")

    """

    _init_thick_mode()

    user = os.getenv("ORACLE_USER")

    password = os.getenv("ORACLE_PASSWORD")

    dsn = os.getenv("ORACLE_DSN")

    if not user or not password or not dsn:

        raise ValueError(

            "Missing required env vars: ORACLE_USER, ORACLE_PASSWORD, ORACLE_DSN"

        )

    return oracledb.connect(

        user=user,

        password=password,

        dsn=dsn

    )


# ============================================================

# RAW ORACLE QUERY

# ============================================================

ORACLE_RAW_QUERY = """
SELECT
   dc.WORK_ORDER,
   op.OPERATION_NUMBER,
   dc.TEXT_SEQ,
   dc.ROW_NO,
   dc.COLUMN_NO,
   dc.DCB_TITLE,
   dc.DCB_TYPE,
   dc.DCB_VALUE,
   dc.LAST_LOAD_DATE
FROM MFG_AI.SHOP_DATA_COLLECT_V dc
INNER JOIN MFG_AI.WIP_OPERATION_RTV op
   ON op.OPERATION_ID = dc.OPERATION_ID
WHERE dc.WORK_ORDER IN ({placeholders})
ORDER BY op.OPERATION_NUMBER, dc.TEXT_SEQ, dc.ROW_NO, dc.COLUMN_NO
""".strip()

# ============================================================

# FETCH FUNCTION (USED BY ADMIN)

# ============================================================

def fetch_oracle_rows(work_orders):

    """

    Pull raw Oracle rows for a list of work orders.

    Returns list of dicts keyed by column name.

    """

    cleaned = [str(x).strip() for x in work_orders if str(x).strip()]

    if not cleaned:

        return []

    placeholders = ", ".join([f":{i+1}" for i in range(len(cleaned))])

    sql = ORACLE_RAW_QUERY.format(placeholders=placeholders)

    conn = get_connection()

    try:

        cur = conn.cursor()

        try:

            cur.execute(sql, cleaned)

            columns = [col[0].upper() for col in cur.description]

            required = {"OPERATION_NUMBER", "DCB_TITLE", "DCB_VALUE"}

            missing = required - set(columns)

            if missing:

                raise ValueError(

                    f"Oracle results missing required columns: {', '.join(sorted(missing))}"

                )

            rows = cur.fetchall()

            results = []

            for row in rows:

                results.append(dict(zip(columns, row)))

            return results

        finally:

            cur.close()

    finally:

        conn.close()
 