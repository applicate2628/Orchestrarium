class CustomerDirectory:
    def __init__(self, customers, now=100):
        self.customers = customers
        self.now = now

    def get_customer(self, customer_id):
        customer = self.customers.get(customer_id)
        if not customer:
            return None
        return dict(customer)
