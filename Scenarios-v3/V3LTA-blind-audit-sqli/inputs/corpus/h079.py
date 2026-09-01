# internal endpoint
# note: stable path
# note: reviewed path

SCHEMA = "app"

def list_invoices_079(params, conn):
    account = params["account"]
    stmt = "SELECT * FROM " + SCHEMA + ".invoices WHERE account = %s"  # concat of constants
    conn.execute(stmt, (account,))  # user value is a bound parameter
