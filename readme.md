# Supply Chain Inventory Optimization & Analytics Dashboard

## Project Goal

A practical Data Analyst portfolio project for monitoring inventory exposure, identifying replenishment priorities, and evaluating supplier risk.

This is intentionally positioned between a basic EDA project and an advanced optimization/ML system. The business logic is explainable in a fresher interview.

## Main Features

### 1. Control Center
- Inventory exposure
- Critical / low / healthy / overstock SKUs
- Estimated replenishment value
- Stock position against reorder point
- Top replenishment priorities

### 2. Replenishment Planner
- Purchasing queue
- Current stock vs reorder point
- Safety stock
- Target stock
- Suggested order quantity
- Estimated purchase value
- CSV export

### 3. Stock Risk Map
- Inventory risk score
- Lead-time risk
- Demand variability
- SKU-level risk ranking

### 4. Supplier Risk
- Lead-time comparison
- On-time delivery
- Quality rate
- Critical SKUs by supplier
- Supplier risk index

### 5. SKU Detail
- Monthly demand trend
- 3-month moving average
- Stock position
- Reorder point
- Safety stock
- Order recommendation
- Inventory turnover and days on hand

## Core Analytics

**Reorder Point**

Average Daily Demand × Lead Time + Safety Stock

**Safety Stock**

Uses demand variability, lead time, and a service-level z-score approximation.

**Inventory Turnover**

Annual Cost of Goods Sold / Inventory Value

**Days on Hand**

365 / Inventory Turnover

**ABC Classification**

SKUs are ranked by annual consumption cost:
- A: first ~70% of cumulative value
- B: next ~20%
- C: remaining ~10%

**Inventory Risk Score**

Combines:
- stock gap relative to reorder point
- supplier lead time
- demand variability

The score is a prioritization aid, not a financial or operational guarantee.

## Dataset

Synthetic, reproducible portfolio data:
- 35 products
- 5 categories
- 6 suppliers
- 24 months of demand
- product costs and prices
- supplier lead times
- current stock
- service-level assumptions

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Interview Explanation

**Problem:** Poor inventory planning can create two opposite problems: stock-outs and excess inventory.

**Approach:** I combined historical demand with product and supplier data, calculated inventory KPIs, estimated safety stock and reorder points, classified SKUs by value, and built a replenishment/risk workflow.

**Output:** An interactive inventory control center that helps prioritize which SKUs need action and why.

## Production Limitations

A real inventory system would also consider:
- open purchase orders
- minimum order quantities
- supplier contracts
- promotions
- warehouse capacity
- multiple warehouses
- seasonality
- actual service-level targets
- purchase-order history

Those are deliberately outside this fresher-level portfolio scope.