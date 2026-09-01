# Scalability Notes

- the scenario corpus grows as additional routing-basis `N` roots are added
- the lane matrix is rebuilt after each routing-translation refresh
- storing full serialized card payloads repeatedly will compound memory cost over long sessions
