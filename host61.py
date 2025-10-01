# Development Charge – always 20% of overheads
full_dev_charge = overheads_m * 0.20

# Default: use full charge
dev_used = full_dev_charge
breakdown["Development Charge"] = full_dev_charge

# Apply reductions
reduction_val = 0.0
if employment_support == "Employment on release/RoTL":
    reduction_val = -abs(overheads_m * 0.10)
elif employment_support == "Post release":
    reduction_val = -abs(overheads_m * 0.10)
elif employment_support == "Both":
    reduction_val = -abs(overheads_m * 0.20)

if reduction_val != 0.0:
    # Swap to revised logic
    revised_dev_charge = full_dev_charge + reduction_val
    breakdown["Development Charge Reduction (Support Applied)"] = reduction_val
    breakdown["Revised Development Charge"] = revised_dev_charge
    dev_used = revised_dev_charge

# Totals use `dev_used`, not both
subtotal = (
    breakdown["Prisoner Wages"]
    + breakdown["Instructor Salary"]
    + breakdown["Overheads (61%)"]
    + dev_used
)