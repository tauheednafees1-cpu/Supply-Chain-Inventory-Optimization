import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="Inventory Control Center",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

DATA = "data"

@st.cache_data
def load_data():
    products = pd.read_csv(f"{DATA}/products.csv")
    demand = pd.read_csv(f"{DATA}/monthly_demand.csv", parse_dates=["date"])
    suppliers = pd.read_csv(f"{DATA}/suppliers.csv")
    return products, demand, suppliers

products, demand, suppliers = load_data()

# ---------- Analytics ----------
agg = demand.groupby("product_id").agg(
    annual_units=("units_sold", "sum"),
    avg_monthly_demand=("units_sold", "mean"),
    demand_std=("units_sold", "std"),
    annual_sales=("sales_value", "sum"),
    annual_cost=("cost_value", "sum")
).reset_index()

df = products.merge(agg, on="product_id", how="left")

# More intuitive inventory formulas for a fresher analytics project
df["avg_daily_demand"] = df["annual_units"] / 730
df["daily_demand_std"] = df["demand_std"] / np.sqrt(30)

z = df["service_level"].map({0.90: 1.28, 0.95: 1.65, 0.98: 2.05}).fillna(1.65)
df["safety_stock"] = (z * df["daily_demand_std"] * np.sqrt(df["lead_time_days"])).round()
df["reorder_point"] = (
    df["avg_daily_demand"] * df["lead_time_days"] + df["safety_stock"]
).round()

# Target stock = roughly 1.5 months of demand + safety stock
df["target_stock"] = (df["avg_monthly_demand"] * 1.5 + df["safety_stock"]).round()
df["order_qty"] = (df["target_stock"] - df["current_stock"]).clip(lower=0).round()

df["inventory_value"] = df["current_stock"] * df["unit_cost"]
df["inventory_turnover"] = (
    df["annual_cost"] / df["inventory_value"].replace(0, np.nan)
).round(2)
df["days_on_hand"] = (365 / df["inventory_turnover"].replace(0, np.nan)).round(1)

def stock_state(r):
    if r.current_stock < r.reorder_point:
        return "Critical"
    if r.current_stock < r.target_stock:
        return "Low"
    if r.current_stock > r.target_stock * 1.7:
        return "Overstock"
    return "Healthy"

df["stock_state"] = df.apply(stock_state, axis=1)

# Risk score: combines stock gap, lead time and demand variability
df["stock_gap_pct"] = (
    (df["reorder_point"] - df["current_stock"]) / df["reorder_point"].replace(0, np.nan)
).clip(lower=0)

df["risk_score"] = (
    df["stock_gap_pct"].fillna(0) * 60
    + (df["lead_time_days"] / df["lead_time_days"].max()) * 20
    + (df["demand_std"] / df["demand_std"].max()) * 20
).round(1)

# ABC
abc_base = df.sort_values("annual_cost", ascending=False).copy()
abc_base["cum_pct"] = abc_base["annual_cost"].cumsum() / abc_base["annual_cost"].sum()
abc_base["abc_class"] = np.select(
    [abc_base["cum_pct"] <= .70, abc_base["cum_pct"] <= .90],
    ["A", "B"], default="C"
)
df = df.drop(columns=["abc_class"], errors="ignore").merge(
    abc_base[["product_id", "abc_class"]], on="product_id", how="left"
)

supplier_perf = df.groupby("supplier").agg(
    sku_count=("product_id", "count"),
    inventory_value=("inventory_value", "sum"),
    avg_lead_time=("lead_time_days", "mean"),
    critical_skus=("stock_state", lambda x: (x == "Critical").sum()),
    low_skus=("stock_state", lambda x: (x == "Low").sum())
).reset_index().merge(suppliers, on="supplier", how="left")

supplier_perf["risk_index"] = (
    supplier_perf["critical_skus"] / supplier_perf["sku_count"] * 60
    + (1 - supplier_perf["on_time_rate"]) * 25
    + supplier_perf["avg_lead_time"] / supplier_perf["avg_lead_time"].max() * 15
).round(1)

# ---------- Styling ----------
st.markdown("""
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
.kpi {
    border: 1px solid #d9dee7;
    border-radius: 10px;
    padding: 15px 17px;
    background: #ffffff;
    min-height: 105px;
}
.kpi-label {font-size: 0.78rem; color: #687385; margin-bottom: 7px;}
.kpi-value {font-size: 1.55rem; font-weight: 700; color: #1f2937;}
.kpi-note {font-size: 0.72rem; color: #7b8494; margin-top: 5px;}
.section-title {font-size: 1.05rem; font-weight: 700; margin-top: 12px;}
.alert {
    border-left: 4px solid #c2410c;
    background: #fff7ed;
    padding: 12px 15px;
    border-radius: 6px;
}
</style>
""", unsafe_allow_html=True)

# ---------- Sidebar ----------
st.sidebar.title("📦 Inventory Control")
st.sidebar.caption("Supply Chain Analytics")

page = st.sidebar.radio(
    "Workspace",
    [
        "Control Center",
        "Replenishment Planner",
        "Stock Risk Map",
        "Supplier Risk",
        "SKU Detail"
    ]
)

st.sidebar.divider()
st.sidebar.caption("Filters")

categories = st.sidebar.multiselect(
    "Category",
    sorted(df.category.unique()),
    default=sorted(df.category.unique())
)
abc = st.sidebar.multiselect(
    "ABC class",
    ["A", "B", "C"],
    default=["A", "B", "C"]
)

view = df[df.category.isin(categories) & df.abc_class.isin(abc)].copy()

# ---------- Header ----------
st.title("Supply Chain Inventory Control Center")
st.caption("Monitor stock exposure, identify replenishment priorities, and evaluate supplier risk.")

# ---------- KPI helper ----------
def kpi(label, value, note):
    return f"""
    <div class="kpi">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-note">{note}</div>
    </div>
    """

# ---------- CONTROL CENTER ----------
if page == "Control Center":
    critical = (view.stock_state == "Critical").sum()
    low = (view.stock_state == "Low").sum()
    overstock = (view.stock_state == "Overstock").sum()
    inventory_value = view.inventory_value.sum()
    order_value = (view.order_qty * view.unit_cost).sum()

    k = st.columns(5)
    k[0].markdown(kpi("Inventory Exposure", f"₹{inventory_value/1e5:.1f}L", "Current stock value"), unsafe_allow_html=True)
    k[1].markdown(kpi("Critical SKUs", critical, "Below reorder point"), unsafe_allow_html=True)
    k[2].markdown(kpi("Low Stock", low, "Below target stock"), unsafe_allow_html=True)
    k[3].markdown(kpi("Overstock", overstock, "Above 170% of target"), unsafe_allow_html=True)
    k[4].markdown(kpi("Suggested Purchase", f"₹{order_value/1e5:.1f}L", "Estimated replenishment value"), unsafe_allow_html=True)

    st.divider()

    left, right = st.columns([1.15, 1])

    with left:
        st.subheader("Stock Position by SKU")
        plot = view.sort_values("risk_score", ascending=False).head(20).copy()
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=plot.product_name,
            x=plot.current_stock,
            orientation="h",
            name="Current Stock"
        ))
        fig.add_trace(go.Scatter(
            y=plot.product_name,
            x=plot.reorder_point,
            mode="markers",
            name="Reorder Point",
            marker=dict(size=8)
        ))
        fig.update_layout(
            height=610,
            xaxis_title="Units",
            yaxis_title="",
            legend_title="",
            margin=dict(l=10, r=10, t=20, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Inventory State")
        state = view.stock_state.value_counts().reindex(
            ["Critical", "Low", "Healthy", "Overstock"], fill_value=0
        ).reset_index()
        state.columns = ["state", "skus"]
        fig = px.bar(
            state, x="skus", y="state", orientation="h",
            text="skus",
            title=""
        )
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Top Replenishment Priorities")
        priority = view[view.stock_state.isin(["Critical", "Low"])].copy()
        priority["priority_value"] = priority["order_qty"] * priority["unit_cost"]
        priority = priority.sort_values("risk_score", ascending=False).head(10)

        st.dataframe(
            priority[[
                "product_name", "category", "stock_state",
                "current_stock", "reorder_point", "order_qty", "risk_score"
            ]],
            use_container_width=True,
            hide_index=True
        )

# ---------- REPLENISHMENT ----------
elif page == "Replenishment Planner":
    st.header("Replenishment Planner")
    st.write("A purchasing-oriented view of which SKUs need action and approximately how much to order.")

    action = st.selectbox(
        "Show",
        ["All at-risk SKUs", "Critical only", "Low only", "Healthy / Overstock"]
    )

    if action == "Critical only":
        rp = view[view.stock_state == "Critical"].copy()
    elif action == "Low only":
        rp = view[view.stock_state == "Low"].copy()
    elif action == "Healthy / Overstock":
        rp = view[view.stock_state.isin(["Healthy", "Overstock"])].copy()
    else:
        rp = view[view.stock_state.isin(["Critical", "Low"])].copy()

    rp["estimated_purchase_value"] = rp["order_qty"] * rp["unit_cost"]
    rp = rp.sort_values(["risk_score", "estimated_purchase_value"], ascending=False)

    c1, c2, c3 = st.columns(3)
    c1.metric("SKUs in view", len(rp))
    c2.metric("Units to order", f"{rp.order_qty.sum():,.0f}")
    c3.metric("Purchase value", f"₹{rp.estimated_purchase_value.sum()/1e5:.1f}L")

    st.subheader("Purchase Queue")
    table = rp[[
        "product_id", "product_name", "category", "supplier",
        "current_stock", "avg_monthly_demand", "safety_stock",
        "reorder_point", "target_stock", "order_qty",
        "estimated_purchase_value", "stock_state", "risk_score"
    ]].copy()

    st.dataframe(table, use_container_width=True, hide_index=True)

    st.download_button(
        "⬇ Download purchase queue",
        table.to_csv(index=False).encode("utf-8"),
        "replenishment_plan.csv",
        "text/csv"
    )

    st.info(
        "Planning logic is intentionally explainable: target stock is based on recent average demand plus safety stock. "
        "A real procurement system would additionally incorporate MOQ, supplier contracts, open POs and warehouse capacity."
    )

# ---------- STOCK RISK ----------
elif page == "Stock Risk Map":
    st.header("Stock Risk Map")
    st.caption("Risk is higher when a SKU is below its reorder point, has long lead time, and has volatile demand.")

    fig = px.scatter(
        view,
        x="lead_time_days",
        y="risk_score",
        size="inventory_value",
        color="stock_state",
        hover_name="product_name",
        hover_data=["current_stock", "reorder_point", "avg_monthly_demand", "demand_std"],
        labels={
            "lead_time_days": "Supplier Lead Time (days)",
            "risk_score": "Inventory Risk Score"
        },
        title="Inventory Risk vs Supplier Lead Time"
    )
    fig.update_layout(height=560)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Where attention is needed")
    risk = view.sort_values("risk_score", ascending=False).head(15)
    st.dataframe(
        risk[[
            "product_name", "category", "supplier", "stock_state",
            "current_stock", "reorder_point", "lead_time_days",
            "demand_std", "risk_score"
        ]],
        use_container_width=True,
        hide_index=True
    )

# ---------- SUPPLIER ----------
elif page == "Supplier Risk":
    st.header("Supplier Risk & Reliability")

    fig = px.scatter(
        supplier_perf,
        x="avg_lead_time",
        y="on_time_rate",
        size="inventory_value",
        color="risk_index",
        hover_name="supplier",
        labels={
            "avg_lead_time": "Average Lead Time (days)",
            "on_time_rate": "On-Time Delivery Rate",
            "risk_index": "Risk Index"
        },
        title="Supplier Reliability Matrix"
    )
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)

    display = supplier_perf[[
        "supplier", "sku_count", "critical_skus", "low_skus",
        "avg_lead_time", "on_time_rate", "quality_rate", "risk_index"
    ]].copy()

    display["on_time_rate"] = (display.on_time_rate * 100).round(1).astype(str) + "%"
    display["quality_rate"] = (display.quality_rate * 100).round(1).astype(str) + "%"

    st.subheader("Supplier Scorecard")
    st.dataframe(
        display.sort_values("risk_index"),
        use_container_width=True,
        hide_index=True
    )

    worst = supplier_perf.sort_values("risk_index", ascending=False).iloc[0]
    st.markdown(
        f'<div class="alert"><b>Highest supplier risk:</b> {worst.supplier} — '
        f'{int(worst.critical_skus)} critical SKU(s), average lead time '
        f'{worst.avg_lead_time:.1f} days, risk index {worst.risk_index:.1f}.</div>',
        unsafe_allow_html=True
    )

# ---------- SKU DETAIL ----------
else:
    st.header("SKU Detail")
    selected = st.selectbox("Select SKU", view.sort_values("product_name").product_name.tolist())
    p = view[view.product_name == selected].iloc[0]
    history = demand[demand.product_id == p.product_id].sort_values("date").copy()
    history["3_month_avg"] = history.units_sold.rolling(3).mean()

    st.subheader(selected)

    c = st.columns(6)
    c[0].metric("Current Stock", f"{p.current_stock:,.0f}")
    c[1].metric("Reorder Point", f"{p.reorder_point:,.0f}")
    c[2].metric("Safety Stock", f"{p.safety_stock:,.0f}")
    c[3].metric("Order Qty", f"{p.order_qty:,.0f}")
    c[4].metric("Lead Time", f"{p.lead_time_days} days")
    c[5].metric("Status", p.stock_state)

    left, right = st.columns([1.4, 1])

    with left:
        fig = px.line(
            history,
            x="date",
            y=["units_sold", "3_month_avg"],
            title="Monthly Demand and 3-Month Average",
            labels={"value": "Units", "variable": ""}
        )
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("SKU Profile")
        profile = pd.DataFrame({
            "Metric": [
                "Category", "Supplier", "ABC Class",
                "Annual Units", "Annual Sales",
                "Inventory Turnover", "Days on Hand",
                "Unit Cost", "Unit Price"
            ],
            "Value": [
                p.category, p.supplier, p.abc_class,
                f"{p.annual_units:,.0f}", f"₹{p.annual_sales:,.0f}",
                f"{p.inventory_turnover:.2f}x", f"{p.days_on_hand:.1f} days",
                f"₹{p.unit_cost:,.2f}", f"₹{p.unit_price:,.2f}"
            ]
        })
        st.dataframe(profile, use_container_width=True, hide_index=True)

    st.info(
        f"Recommendation: **{p.stock_state}**. "
        f"Current stock is {p.current_stock:,.0f} units against a reorder point of "
        f"{p.reorder_point:,.0f}. Suggested order quantity: {p.order_qty:,.0f} units."
    )

st.divider()
st.caption("Portfolio project • Synthetic demonstration data • Inventory calculations are intentionally explainable.")