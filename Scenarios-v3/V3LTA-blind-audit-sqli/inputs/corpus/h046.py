# internal endpoint
# note: reviewed path
# note: reviewed path
# note: stable path
# note: reviewed path
# note: revised path

SCHEMA = "app"

def list_invoices_046(params, conn):
    account = params["account"]
    stmt = "SELECT * FROM " + SCHEMA + ".invoices WHERE account = %s"  # concat of constants
    conn.execute(stmt, (account,))  # user value is a bound parameter
