import frappe


def get_context(context):
    context.no_cache = True
    context.username = "Palash"
    search_text = frappe.request.args["searchtext"]
    items = get_items(search_text)
    if "columns" in items and "data" in items:
        context.columns = items["columns"]
        context.data = items["data"]

def get_items(search_value=""):
    data = dict()

    if search_value:
        data = search_barcode(search_value)

    item_code = data.get("item_code") if data.get("item_code") else search_value
    barcode = data.get("barcode") if data.get("barcode") else ""

    condition = get_conditions(item_code, barcode)

    result = []

    items_data = frappe.db.sql(
        """
		SELECT
			name AS item_code,
			item_name,
			stock_uom,
			idx AS idx,
			is_stock_item
		FROM
			`tabItem`
		WHERE
			disabled = 0
				AND has_variants = 0
				AND is_sales_item = 1
				AND {condition}
		ORDER BY
			idx desc""".format(
            condition=condition
        ),
        as_dict=1,
    )

    if items_data:
        table_columns = ["Item Code", "Item Name"]
        table_data = []
        items = [d.item_code for d in items_data]
        item_prices_data = frappe.get_all(
            "Item Price",
            fields=["item_code", "price_list_rate", "currency"],
            filters={"price_list": "Selling", "item_code": ["in", items]},
        )

        item_prices, bin_data = {}, {}
        for d in item_prices_data:
            item_prices[d.item_code] = d
        # prepare filter for bin query
        bin_filters = {"item_code": ["in", items]}

        # query item bin
        bin_data = frappe.get_all(
            "Bin",
            fields=["item_code", "warehouse", "sum(actual_qty) as actual_qty"],
            filters=bin_filters,
            group_by="item_code, warehouse"
        )

        warehouse_wise_items = {}

        # convert list of dict into dict as {item_code: actual_qty}
        bin_dict = {}
        for b in bin_data:
            warehouse = b.get("warehouse")
            item_code = b.get("item_code")
            qty = b.get("actual_qty")
            if warehouse not in warehouse_wise_items:
                warehouse_wise_items[warehouse] = {}
            warehouse_wise_items[warehouse][item_code] = qty
            bin_dict[b.get("item_code")] = b.get("actual_qty")
        
        warehouses = warehouse_wise_items.keys()

        for warehouse in warehouses:
            table_columns.append(warehouse)

        for item in items_data:
            item_row = []
            item_code = item.item_code
            item_name = item.item_name            
            item_row.extend([item_code, item_name])
            for warehouse in warehouses:
                warehouse_qty = 0
                if item_code in warehouse_wise_items[warehouse]:
                    warehouse_qty = warehouse_wise_items[warehouse][item_code]
                item_row.append(warehouse_qty)
            table_data.append(item_row)

        res = {"data": table_data, "columns": table_columns}
        return res
    else:
        return {}

def search_barcode(search_value):
    # search barcode no
    barcode_data = frappe.db.get_value(
        "Item Barcode",
        {"barcode": search_value},
        ["barcode", "parent as item_code"],
        as_dict=True,
    )
    if barcode_data:
        return barcode_data

    return {}

def get_conditions(item_code, barcode):
    if barcode:
        return "name = {0}".format(frappe.db.escape(item_code))

    return """(name like {item_code}
		or item_name like {item_code})""".format(
        item_code=frappe.db.escape("%" + item_code + "%")
    )