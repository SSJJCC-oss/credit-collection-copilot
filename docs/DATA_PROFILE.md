# Data profile: `crm_demo.db`

## 1. Tables

| table | rows |
|---|---|
| customers | 303 |
| expenses | 556 |
| items | 400 |
| payments | 28385 |
| purchase_lines | 5576 |
| purchase_orders | 478 |
| sales_order_lines | 188041 |
| sales_orders | 26770 |
| stock | 1200 |
| suppliers | 25 |
| synthetic_notes | 334 |
| users | 8 |
| warehouses | 3 |

### customers

Columns: `id` INTEGER (PK), `code` TEXT, `name` TEXT, `customer_type` TEXT, `contact_person` TEXT, `phone` TEXT, `email` TEXT, `city` TEXT, `credit_limit` REAL, `credit_days` INTEGER, `status` TEXT, `home_warehouse_id` INTEGER, `created_at` TEXT

| id | code | name | customer_type | contact_person | phone | email | city | credit_limit | credit_days | status | home_warehouse_id | created_at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | C0001 | Harbor View Mini Mart | Mini Mart | Joseph Aziz | +971 53 587 5896 | info1@example.test | Dubai | 6500.0 | 15 | confirmed | 2 | 2024-02-02 |
| 2 | C0002 | Pearl Bakery | Bakery | Tariq Menon | +971 51 875 8357 | info2@example.test | Sharjah | 42000.0 | 30 | confirmed | 1 | 2024-01-08 |
| 3 | C0003 | Sunrise Restaurant | Restaurant | Priya Menon | +971 59 364 6238 | info3@example.test | Ras Al Khaimah | 49500.0 | 15 | confirmed | 1 | 2024-10-05 |

### expenses

Columns: `id` INTEGER (PK), `expense_date` TEXT, `category` TEXT, `description` TEXT, `amount` REAL, `warehouse_id` INTEGER

| id | expense_date | category | description | amount | warehouse_id |
|---|---|---|---|---|---|
| 1 | 2024-10-21 | Rent | Rent - Oct 2024 | 10297.82 | 1 |
| 2 | 2024-10-25 | Salaries | Salaries - Oct 2024 | 28485.03 | 1 |
| 3 | 2024-10-09 | Fuel & transport | Fuel & transport - Oct 2024 | 2690.25 | 1 |

### items

Columns: `id` INTEGER (PK), `sku` TEXT, `name` TEXT, `category` TEXT, `unit` TEXT, `cost_price` REAL, `sale_price` REAL, `reorder_level` INTEGER, `supplier_id` INTEGER, `active` INTEGER

| id | sku | name | category | unit | cost_price | sale_price | reorder_level | supplier_id | active |
|---|---|---|---|---|---|---|---|---|---|
| 1 | SKU00001 | PrimeChoice Basmati rice 5kg | Rice & grains | bag | 19.58 | 22.6 | 80 | 12 | 1 |
| 2 | SKU00002 | FreshPick Sunflower oil 1L | Cooking oil | bottle | 8.0 | 8.74 | 20 | 10 | 1 |
| 3 | SKU00003 | GoldenFarm Cornflour 1kg | Flour & baking | bag | 8.65 | 10.27 | 80 | 8 | 1 |

### payments

Columns: `id` INTEGER (PK), `customer_id` INTEGER, `order_id` INTEGER, `payment_date` TEXT, `amount` REAL, `method` TEXT

| id | customer_id | order_id | payment_date | amount | method |
|---|---|---|---|---|---|
| 1 | 291 | 28 | 2024-10-26 | 400.91 | Cheque |
| 2 | 93 | 37 | 2024-10-28 | 956.53 | Bank transfer |
| 3 | 56 | 74 | 2024-10-28 | 1036.01 | Cheque |

### purchase_lines

Columns: `id` INTEGER (PK), `po_id` INTEGER, `item_id` INTEGER, `quantity` INTEGER, `unit_cost` REAL, `line_total` REAL

| id | po_id | item_id | quantity | unit_cost | line_total |
|---|---|---|---|---|---|
| 1 | 1 | 13 | 50 | 3.0 | 150.0 |
| 2 | 1 | 78 | 50 | 3.06 | 153.0 |
| 3 | 1 | 183 | 100 | 45.47 | 4547.0 |

### purchase_orders

Columns: `id` INTEGER (PK), `po_no` TEXT, `supplier_id` INTEGER, `warehouse_id` INTEGER, `order_date` TEXT, `status` TEXT, `total` REAL

| id | po_no | supplier_id | warehouse_id | order_date | status | total |
|---|---|---|---|---|---|---|
| 1 | PO-00001 | 12 | 2 | 2024-10-23 | received | 113132.5 |
| 2 | PO-00002 | 10 | 1 | 2024-10-19 | received | 49878.5 |
| 3 | PO-00003 | 3 | 1 | 2024-10-04 | received | 80391.5 |

### sales_order_lines

Columns: `id` INTEGER (PK), `order_id` INTEGER, `item_id` INTEGER, `quantity` INTEGER, `unit_price` REAL, `line_total` REAL

| id | order_id | item_id | quantity | unit_price | line_total |
|---|---|---|---|---|---|
| 1 | 1 | 141 | 18 | 3.24 | 58.32 |
| 2 | 1 | 257 | 12 | 24.73 | 296.76 |
| 3 | 1 | 350 | 14 | 13.0 | 182.0 |

### sales_orders

Columns: `id` INTEGER (PK), `order_no` TEXT, `customer_id` INTEGER, `warehouse_id` INTEGER, `order_date` TEXT, `due_date` TEXT, `status` TEXT, `subtotal` REAL, `tax_amount` REAL, `total` REAL, `paid_amount` REAL, `created_by` INTEGER

| id | order_no | customer_id | warehouse_id | order_date | due_date | status | subtotal | tax_amount | total | paid_amount | created_by |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | SO-000001 | 16 | 2 | 2024-10-26 | 2024-11-25 | delivered | 3045.27 | 152.26 | 3197.53 | 3197.53 | 3 |
| 2 | SO-000002 | 18 | 2 | 2024-10-26 | 2024-11-10 | delivered | 295.06 | 14.75 | 309.81 | 309.81 | 2 |
| 3 | SO-000003 | 33 | 3 | 2024-10-26 | 2024-11-25 | delivered | 411.52 | 20.58 | 432.1 | 432.1 | 5 |

### stock

Columns: `warehouse_id` INTEGER (PK), `item_id` INTEGER (PK), `quantity` INTEGER

| warehouse_id | item_id | quantity |
|---|---|---|
| 1 | 1 | 151 |
| 1 | 2 | 73 |
| 1 | 3 | 456 |

### suppliers

Columns: `id` INTEGER (PK), `name` TEXT, `phone` TEXT, `city` TEXT

| id | name | phone | city |
|---|---|---|---|
| 1 | Malik Foods Trading 1 | +971 58 303 9928 | Abu Dhabi |
| 2 | Sharma Wholesale 2 | +971 59 384 1106 | Sharjah |
| 3 | Pillai Industries 3 | +971 54 259 4527 | Ajman |

### synthetic_notes

Columns: `kind` TEXT, `ref_table` TEXT, `ref_id` INTEGER, `note` TEXT

| kind | ref_table | ref_id | note |
|---|---|---|---|
| churned | customers | 3 | Stopped ordering after 2025-12-05 |
| churned | customers | 6 | Stopped ordering after 2026-01-15 |
| churned | customers | 9 | Stopped ordering after 2026-08-21 |

### users

Columns: `id` INTEGER (PK), `name` TEXT, `role` TEXT, `email` TEXT, `active` INTEGER

| id | name | role | email | active |
|---|---|---|---|---|
| 1 | Fatima Nair | Admin | user1@example.test | 1 |
| 2 | Ahmed Patel | Sales manager | user2@example.test | 1 |
| 3 | Hassan Sharma | Sales rep | user3@example.test | 1 |

### warehouses

Columns: `id` INTEGER (PK), `name` TEXT, `city` TEXT, `is_main` INTEGER

| id | name | city | is_main |
|---|---|---|---|
| 1 | Main Warehouse | Dubai | 1 |
| 2 | North Depot | Dubai | 0 |
| 3 | Port Warehouse | Ajman | 0 |

## 2. Views (saved queries)

**v_outstanding_orders**
```sql
CREATE VIEW v_outstanding_orders AS
  SELECT o.id, o.order_no, c.name AS customer, o.order_date, o.due_date, o.total, o.paid_amount,
         ROUND(o.total - o.paid_amount, 2) AS balance
  FROM sales_orders o JOIN customers c ON c.id = o.customer_id
  WHERE o.status IN ('confirmed', 'delivered') AND o.total - o.paid_amount > 0.005
```
**v_low_stock**
```sql
CREATE VIEW v_low_stock AS
  SELECT s.warehouse_id, w.name AS warehouse, i.id AS item_id, i.name AS item, s.quantity, i.reorder_level
  FROM stock s JOIN items i ON i.id = s.item_id JOIN warehouses w ON w.id = s.warehouse_id
  WHERE i.active = 1 AND s.quantity < i.reorder_level
```
**v_sales_monthly**
```sql
CREATE VIEW v_sales_monthly AS
  SELECT substr(order_date, 1, 7) AS month, COUNT(*) AS orders, ROUND(SUM(total), 2) AS sales
  FROM sales_orders WHERE status IN ('confirmed', 'delivered') GROUP BY 1
```

## 3. Inferred relationships (orphan rows should be 0)

| child column | parent | orphans |
|---|---|---|
| sales_orders.customer_id | customers.id | 0 |
| sales_orders.warehouse_id | warehouses.id | 0 |
| sales_orders.created_by | users.id | 0 |
| sales_order_lines.order_id | sales_orders.id | 0 |
| sales_order_lines.item_id | items.id | 0 |
| payments.order_id | sales_orders.id | 0 |
| payments.customer_id | customers.id | 0 |
| customers.home_warehouse_id | warehouses.id | 0 |
| items.supplier_id | suppliers.id | 0 |
| purchase_orders.supplier_id | suppliers.id | 0 |
| purchase_lines.po_id | purchase_orders.id | 0 |
| purchase_lines.item_id | items.id | 0 |
| stock.item_id | items.id | 0 |
| stock.warehouse_id | warehouses.id | 0 |
| expenses.warehouse_id | warehouses.id | 0 |

## 4. Data-quality checks (rows failing)

| check | failing rows |
|---|---|
| line_total = quantity x unit_price | 0 |
| order subtotal = sum of its lines | 0 |
| tax_amount = 5% of subtotal (UAE VAT) | 0 |
| total = subtotal + tax | 0 |
| paid_amount = sum of payments | 0 |
| due_date = order_date + customer credit_days | 0 |
| payment before order date | 0 |
| customers with no email | 60 |
| customers with no phone | 3 |

## 5. Business snapshot (as of 2026-10-25)

Order status counts:

| status | orders | first | last | total AED | paid AED |
|---|---|---|---|---|---|
| cancelled | 430 | 2024-10-27 | 2026-10-16 | 915803.0 | 0.0 |
| confirmed | 83 | 2026-10-18 | 2026-10-22 | 167001.0 | 0.0 |
| delivered | 26254 | 2024-10-26 | 2026-10-21 | 56384661.0 | 52119721.0 |
| new | 2 | 2026-10-24 | 2026-10-25 | 3982.0 | 0.0 |
| to_confirm | 1 | 2026-10-25 | 2026-10-25 | 378.0 | 0.0 |

Outstanding on delivered orders, aged by days past due date:

| bucket | invoices | balance AED |
|---|---|---|
| 0 not yet due | 551 | 1835763.0 |
| 1-30 | 508 | 1278398.0 |
| 31-60 | 224 | 518636.0 |
| 61-90 | 75 | 122505.0 |
| 90+ | 269 | 509639.0 |

Customers whose unpaid balance is above their credit limit:

| id | name | city | limit | days | open balance |
|---|---|---|---|---|---|
| 122 | Harbor View Supermarket | Dubai | 155000.0 | 30 | 389215.0 |
| 232 | Oasis Hypermarket | Dubai | 76500.0 | 45 | 223769.0 |
| 225 | Date Palm Supermarket Branch 2 | Al Ain | 105000.0 | 45 | 225496.0 |
| 24 | Green Valley Hypermarket | Ajman | 118500.0 | 45 | 215579.0 |
| 42 | Date Palm Supermarket | Ras Al Khaimah | 117500.0 | 45 | 205605.0 |
| 211 | Bright Day Hypermarket | Ras Al Khaimah | 77000.0 | 15 | 158450.0 |
| 86 | Pearl Supermarket Branch 2 | Ajman | 140000.0 | 45 | 205186.0 |
| 104 | Sunrise Supermarket I | Dubai | 20000.0 | 15 | 77638.0 |
| 29 | Golden Palm Supermarket | Sharjah | 10000.0 | 30 | 62849.0 |
| 118 | Metro Bakery | Al Ain | 27500.0 | 15 | 69468.0 |
| 209 | Lotus Restaurant Express | Ajman | 37500.0 | 30 | 79155.0 |
| 73 | Palm Grove Restaurant Express | Ras Al Khaimah | 10500.0 | 30 | 43797.0 |
| 120 | Union Supermarket | Al Ain | 59500.0 | 60 | 90881.0 |
| 12 | Golden Palm Catering | Abu Dhabi | 37000.0 | 7 | 64301.0 |
| 231 | Royal Supermarket | Abu Dhabi | 106000.0 | 30 | 132453.0 |
| 261 | Harbor View Supermarket Express | Sharjah | 17000.0 | 30 | 42085.0 |
| 23 | Pearl Supermarket | Abu Dhabi | 10000.0 | 30 | 26613.0 |
| 117 | Fresh Basket Bakery | Dubai | 22500.0 | 30 | 32585.0 |
| 146 | Desert Rose Restaurant Express | Dubai | 47500.0 | 30 | 55740.0 |
| 193 | Green Valley Restaurant II | Abu Dhabi | 22000.0 | 30 | 27417.0 |
| 270 | Falcon Grocery Express | Abu Dhabi | 2500.0 | 0 | 7670.0 |
| 251 | Metro Supermarket Branch 2 | Al Ain | 125000.0 | 45 | 127783.0 |
| 148 | Falcon Grocery Branch 2 | Ajman | 6000.0 | 0 | 8140.0 |
| 171 | Corner Grocery Express | Al Ain | 3500.0 | 0 | 5523.0 |

How late customers historically pay (payment date vs due date):

| lateness | payments |
|---|---|
| 0 on time | 5754 |
| 1-30 late | 13498 |
| 31-60 late | 7129 |
| 61-90 late | 1021 |
| 90+ late | 983 |

Orders waiting for a decision (status new / to_confirm):

| id | order_no | customer_id | date | total | status |
|---|---|---|---|---|---|
| 26768 | SO-026768 | 97 | 2026-10-24 | 1738.38 | new |
| 26769 | SO-026769 | 163 | 2026-10-25 | 378.28 | to_confirm |
| 26770 | SO-026770 | 287 | 2026-10-25 | 2243.51 | new |

Labels in `synthetic_notes` (answer key left by the data generator):

| kind | table | rows |
|---|---|---|
| bad_debt | sales_orders | 272 |
| churned | customers | 28 |
| duplicate_customer | customers | 3 |
| late_payer | customers | 22 |
| low_stock | stock | 9 |