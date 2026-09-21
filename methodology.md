# PLOT
![My Photo](plot.png)

# Table
The table is linked in the Zero_Coupon_Yield_Curve Excel file. 

# Methodology
The goal of Mini Project 2 is to develop a detailed automated algorithm to determine the continuously compounded discount rate for each bond payment date (coupons and principal).

After importing all the necessary libraries, the first step is to create two functions, `shift_months` and `bond_cashflows`. 
- The `shift_months` function takes in a date and an integer value for the number of months, which calculates precise future and past coupon dates by adding or subtracting months.
- The `bond_cashflows` function takes in a settlement date, maturity date, and coupon percent to calculate the coupon dates, generated cashflows, and any accrued interest.

The algorithm that we decided to use is the Nelson-Siegel-Svensson (NSS) continuously compounded zero-coupon rate curve. This can be seen in the function `svensson_rate`. This model works by taking in an array of time periods (`t`) and a set of six parameters (`p`) to generate a continuously compounded zero-coupon discount rate for each time period. The six parameters (`b0`, `b1`, `b2`, `b3`, `tau1`, `tau2`) control the macroeconomic shape of the curve: its long-term level, short-term slope, and two humps (curvature) across medium-term maturities.

The full Nelson-Siegel-Svensson equation is below:
$$z(t) = \beta_0 + \beta_1 \left( \frac{1 - e^{-t/\tau_1}}{t/\tau_1} \right) + \beta_2 \left( \frac{1 - e^{-t/\tau_1}}{t/\tau_1} - e^{-t/\tau_1} \right) + \beta_3 \left( \frac{1 - e^{-t/\tau_2}}{t/\tau_2} - e^{-t/\tau_2} \right)$$

After defining a function for calculating the Nelson-Siegel-Svensson rate, we can build the discount curve. We do three things to build the discount curve:
1. **Market Price**: The function calculates the observed "market clean price" for each bond by taking the midpoint between the bid and ask quotes.
2. **Mapping**: It loops through every bond in the dataframe, calling `bond_cashflows` to generate its schedule of payments.
3. **Time Conversion**: It converts those payment dates into continuous years from settlement, storing all this data in a list called `bonds`.

Inside the `build_discount_curve` function, there is a nested function called `residuals` that allows us to find the best-fit curve by calculating the pricing errors for all bonds, and storing it in a numpy array.

- The `residuals` function discounts the generated cash flows using trial NSS parameters to find a model-implied dirty price, subtracts the accrued interest to get a model clean price, and then compares that to the actual observed market price.

Then, we use the `least_squares` optimization algorithm from the SciPy library to iteratively adjust the six NSS parameters based on the errors returned by the `residuals` function.

Finally, we plot the values and save the final pandas dataframe as an Excel file.