import calendar
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import least_squares


INPUT_FILE = Path("data/Treasury data 090426.xlsx")
SETTLEMENT = date(2026, 9, 8)
YEAR_BASIS = 365.25



# Shift a date by whole months.
# Treasury notes and bonds pay coupons every six months.

def shift_months(d, months):
    """Shift a date by whole months while preserving month-end dates."""
    
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1

    if d.day == calendar.monthrange(d.year, d.month)[1]:
        day = calendar.monthrange(y, m)[1]
    else:
        day = min(d.day, calendar.monthrange(y, m)[1])

    return date(y, m, day)


# Generate all remaining coupon and principal cash flows.
# Also calculate accrued interest.
def bond_cashflows(settlement, maturity, coupon_pct):
    """
    Return future payment dates, cash flows,
    and accrued interest per $100 face value.
    """

    # Find the first coupon date after settlement.
    next_coupon = maturity

    while shift_months(next_coupon, -6) > settlement:
        next_coupon = shift_months(next_coupon, -6)

    previous_coupon = shift_months(next_coupon, -6)


    # Generate all future coupon/payment dates.
    dates = []
    d = next_coupon

    while d < maturity:
        dates.append(d)
        d = shift_months(d, 6)

    dates.append(maturity)


    # Semiannual coupon payment.
    coupon = coupon_pct / 2

    cashflows = np.full(
        len(dates),
        coupon,
        dtype=float
    )

    # Add $100 principal to the final payment.
    cashflows[-1] += 100


    # Actual/Actual accrued interest.
    accrued = (
        coupon
        * (settlement - previous_coupon).days
        / (next_coupon - previous_coupon).days
    )

    return dates, cashflows, accrued


# ---------------------------------------------------------
# Nelson-Siegel-Svensson continuously compounded zero-coupon rate curve.
# ---------------------------------------------------------
def svensson_rate(t, p):
    """
    Continuously compounded zero/discount rate z(t).
    """

    b0, b1, b2, b3, tau1, tau2 = p

    t = np.asarray(t, dtype=float)

    x1 = t / tau1
    x2 = t / tau2

    L1 = (1 - np.exp(-x1)) / x1
    L2 = L1 - np.exp(-x1)
    L3 = (
        (1 - np.exp(-x2)) / x2
        - np.exp(-x2)
    )

    return (
        b0
        + b1 * L1
        + b2 * L2
        + b3 * L3
    )

def build_discount_curve(input_file, settlement):
    """
    Fit all Treasury notes/bonds and return the
    continuously compounded discount rate for every
    distinct future coupon/principal payment date.
    """

    # =====================================================
    # 1. Read the Treasury data
    # =====================================================

    raw = pd.read_excel(
        input_file,
        sheet_name="Sheet1",
        header=None
    )

    # We only need:
    # Maturity, Coupon, Bid, Asked
    df = raw.iloc[:, 1:5].copy()

    df.columns = [
        "Maturity",
        "Coupon",
        "Bid",
        "Asked"
    ]


    # Convert the relevant columns to numeric values.
    df["Coupon"] = pd.to_numeric(
        df["Coupon"],
        errors="coerce"
    )

    df["Bid"] = pd.to_numeric(
        df["Bid"],
        errors="coerce"
    )

    df["Asked"] = pd.to_numeric(
        df["Asked"],
        errors="coerce"
    )


    # Remove headings / blank rows / unusable observations.
    df = df.dropna(
        subset=[
            "Maturity",
            "Coupon",
            "Bid",
            "Asked"
        ]
    ).copy()


    # Convert maturity to Python dates.
    df["Maturity"] = pd.to_datetime(
        df["Maturity"]
    ).dt.date


    # 2. Market clean price
    # Use the midpoint of bid and ask as market price.
    df["MarketPrice"] = (
        df["Bid"] + df["Asked"]
    ) / 2

    # 3. Generate all cash flows for every bond

    bonds = []

    for _, row in df.iterrows():

        dates, cfs, accrued = bond_cashflows(
            settlement,
            row["Maturity"],
            float(row["Coupon"])
        )


        # Convert each payment date to years from settlement.
        times = np.array([
            (d - settlement).days / YEAR_BASIS
            for d in dates
        ])


        bonds.append(
            (
                dates,
                cfs,
                times,
                float(row["MarketPrice"]),
                accrued
            )
        )


    # 4. Pricing errors for a candidate Svensson curve

    def residuals(p):

        errors = []

        for (
            dates,
            cfs,
            times,
            market_price,
            accrued
        ) in bonds:

            # Discount every coupon and principal payment
            # using the continuously compounded spot rate.
            model_dirty_price = np.sum(
                cfs
                * np.exp(
                    -svensson_rate(times, p)
                    * times
                )
            )


            # Treasury market quotations are clean prices,
            # so subtract accrued interest.
            model_clean_price = (
                model_dirty_price - accrued
            )


            # Difference between theoretical and market price.
            errors.append(
                model_clean_price - market_price
            )

        return np.array(errors)

    # 5. Estimate the Svensson parameters

    # Starting values.
    # Some manual experimentation may be required.
    initial = np.array([
        0.03,
        0.006,
        0.025,
        0.08,
        1.0,
        17.0
    ])


    # Parameter bounds.
    lower = np.array([
        -0.10,
        -0.20,
        -0.20,
        -0.20,
        0.05,
        0.05
    ])

    upper = np.array([
        0.20,
        0.20,
        0.20,
        0.20,
        30.0,
        60.0
    ])


    # Minimize the sum of squared pricing errors.
    fit = least_squares(
        residuals,
        initial,
        bounds=(lower, upper),
        max_nfev=10000
    )


    # Fitted Svensson parameters.
    p = fit.x


    # 6. Find every distinct coupon/principal payment date

    payment_dates = sorted({
        d
        for dates, *_ in bonds
        for d in dates
    })


    # Convert payment dates into years from settlement.
    t = np.array([
        (d - settlement).days / YEAR_BASIS
        for d in payment_dates
    ])


    # 7. Continuously compounded discount rate
    #    for every payment date

    z = svensson_rate(t, p)


    # 8. Final table

    return pd.DataFrame({
        "Payment Date": payment_dates,
        "Years from Settlement": t,
        "CC Discount Rate (%)": 100 * z
    })

curve = build_discount_curve(
    INPUT_FILE,
    SETTLEMENT
)

curve.to_excel("Zero_Coupon_Yield_Curve.xlsx", index=False)

pd.set_option(
    "display.max_rows",
    300
)

print(
    curve.round({
        "Years from Settlement": 4,
        "CC Discount Rate (%)": 4
    })
)

plt.figure(figsize=(10, 5.5))

plt.plot(
    curve["Years from Settlement"],
    curve["CC Discount Rate (%)"]
)

plt.xlabel("Years from Settlement")

plt.ylabel(
    "Continuously Compounded Discount Rate (%)"
)

plt.title(
    "U.S. Treasury Continuously Compounded Discount Curve"
)

plt.grid(alpha=0.25)

plt.tight_layout()

plt.show()