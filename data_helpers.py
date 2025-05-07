def find_type_by_name(data_structs, name):
    """
    Finds and returns the first ClassDefinition, UnionDefinition, or EnumDefinition
    with the given name from the data_structs list.
    Returns None if not found.
    """
    for item in data_structs:
        if hasattr(item, "name") and item.name == name:
            return item
    return None
