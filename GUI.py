from tkinter import END, ttk, IntVar, StringVar, DoubleVar, filedialog
from matplotlib import pyplot as plt
from ttkthemes import ThemedTk
import numpy as np
import os
from tkinter import messagebox
from datetime import timedelta
import pandas as pd
import tkinter as tk
import seaborn as sns
from WelcomePage import WelcomePage
from Workforce_Window import BreakdownJobsPopup  # Import the new class
from FuelCycle_Window import FuelCycleWindow

"""
Nuclear Power Prediction Tool

This script provides a GUI application for simulating and predicting the growth of nuclear reactors' capacities
over time. The application allows users to input reactor types, capacities, and growth rates, and then runs simulations
to project future capacities.

Author: SM
Date: 07-11-2024
"""


class ToolTip:
    """
    A simple tooltip class that displays text when hovering over a widget.
    """
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        # Bind mouse events
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)


    def on_enter(self, event=None):
        self.showtip()

    def on_leave(self, event=None):
        self.hidetip()

    def showtip(self):
        """Display text in a small window near the widget."""
        if self.tipwindow or not self.text:
            return
        # Calculate position
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20

        # Create a Toplevel window (no window manager decorations)
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)  # Remove window decorations
        tw.wm_geometry(f"+{x}+{y}")

        # Customize the tooltip's look
        label = tk.Label(
            tw,
            text=self.text,
            justify='left',
            background="#ffffe0",  # light yellow background
            relief='solid',
            borderwidth=1,
            font=("tahoma", "8", "normal")
        )
        label.pack(ipadx=1, ipady=1)

    def hidetip(self):
        """Destroy the tooltip window."""
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()



def generate_normal_sample(mu, coefficient_of_variation, size):
    # Check if coefficient of variation is non-negative
    if coefficient_of_variation < 0:
        raise ValueError("Coefficient of variation must be non-negative.")

    # Calculate the standard deviation
    std = mu * coefficient_of_variation

    # Generate sample from normal distribution
    return np.random.normal(mu, std, size)


def calculate_cumulative_total_capacity(data):

    cumulative_total_capacities = {}
    # Iterate over each scenario (each 2D array in the 3D array)
    for index, scenario in enumerate(data):
        # Sum across columns for each row to get total capacity for each year in the scenario
        total_capacity_by_year = scenario.sum(axis=1)
        # Calculate the cumulative sum across years
        cumulative_capacity_by_year = np.cumsum(total_capacity_by_year)
        # Store in dictionary with the scenario index as key
        cumulative_total_capacities[f"Scenario {index + 1}"] = cumulative_capacity_by_year.tolist()

    return cumulative_total_capacities



def vectorized_full_simulate_reactor_growth(reactor_types, reactor_parameters, specific_years, num_simulations,
                                            growth_functions, capacities_array, total_capacity_goal, years_difference,
                                            mean_growth_rate, cov_growth_rate):

    std_growth_rate = mean_growth_rate * cov_growth_rate

    samples_array = np.zeros((len(reactor_types), num_simulations))
    for i, reactor in enumerate(reactor_types):
        # Sample from the user-provided normal distribution (mean and std)
        samples_array[i] = np.random.normal(mean_growth_rate, std_growth_rate, num_simulations)

    number_of_reactors = np.zeros((len(reactor_types), num_simulations, len(years_difference)))
    for i, reactor in enumerate(reactor_types):
        if growth_functions[i] == 'Exponential':
            # Calculate cumulative growth
            cumulative_reactors = np.exp(samples_array[i][:, np.newaxis] * years_difference.T) - 1
            # Calculate yearly increments
            number_of_reactors[i] = np.diff(cumulative_reactors, axis=1, prepend=0)
        elif growth_functions[i] == 'Logarithmic':
            # Calculate cumulative growth
            cumulative_reactors = samples_array[i][:, np.newaxis] * np.log(1 + years_difference.T)
            # Calculate yearly increments
            number_of_reactors[i] = np.diff(cumulative_reactors, axis=1, prepend=0)
        elif growth_functions[i] == 'Linear':
            # Calculate cumulative growth
            cumulative_reactors = samples_array[i][:, np.newaxis] * years_difference.T
            # Calculate yearly increments
            number_of_reactors[i] = np.diff(cumulative_reactors, axis=1, prepend=0)

        else:
            print(f"Error: Unexpected growth type for reactor {reactor}.")
            return None, None, None

    capacities_array = np.array(capacities_array)[:, np.newaxis, np.newaxis]

    yearly_f_values_array = number_of_reactors * capacities_array
    yearly_f_values_array = np.transpose(yearly_f_values_array, (1, 2, 0))

    total_capacities = total_capacity_goal
    scale_factors = total_capacities[:, np.newaxis, np.newaxis] / yearly_f_values_array.sum(axis=(1, 2))[:, np.newaxis, np.newaxis]
    scaled_values_array = yearly_f_values_array * scale_factors

    cumulative_remainders = np.zeros((num_simulations, len(specific_years), len(reactor_types)))

    for sim in range(num_simulations):
        for year_index in range(len(specific_years)):
            for reactor_index in range(len(reactor_types)):
                if year_index > 0:
                    scaled_values_array[sim, year_index, reactor_index] += cumulative_remainders[sim, year_index - 1, reactor_index] * capacities_array[reactor_index]

                total_reactors_needed = scaled_values_array[sim, year_index, reactor_index] / capacities_array[reactor_index]
                reactors_to_deploy = np.floor(total_reactors_needed)

                remainder = total_reactors_needed - reactors_to_deploy
                cumulative_remainders[sim, year_index, reactor_index] = remainder

                if cumulative_remainders[sim, year_index, reactor_index] >= 1:
                    reactors_to_deploy += np.floor(cumulative_remainders[sim, year_index, reactor_index])
                    cumulative_remainders[sim, year_index, reactor_index] -= np.floor(cumulative_remainders[sim, year_index, reactor_index])

                scaled_values_array[sim, year_index, reactor_index] = reactors_to_deploy * capacities_array[reactor_index]

    deployed_reactors = np.floor(scaled_values_array / capacities_array.T)

    # Create a dictionary to store percentages of total capacity for each reactor type
    deployments_per_type = {}

    for i, reactor_type in enumerate(reactor_types):
        # Sum the number of deployed reactors over all years for each reactor type
        total_deployments = deployed_reactors[:, :, i].sum(axis=1)

        # Calculate the total capacity contributed by this reactor type
        capacity_contributed_by_type = total_deployments * capacities_array[i][0][0]

        # Sum the capacities of all reactor types for each simulation
        total_capacity_per_simulation = scaled_values_array.sum(axis=(1, 2))

        # Calculate the percentage of total capacity for this reactor type
        capacity_percentage = (capacity_contributed_by_type / total_capacity_per_simulation) * 100

        # Store the results in the dictionary with reactor type as the key
        deployments_per_type[reactor_type] = capacity_percentage

    return scaled_values_array, deployed_reactors, deployments_per_type



class ReactorGUI:

    def __init__(self, root):
        self.root = root

        root.title("RENEWS: Reactor Expansion & Nuclear Employment Workforce Simulator")
        self.capacity_factor = 0.927
        self.hours_in_year = 8760
        # Apply a theme
        root.set_theme("breeze")
        self.uranium_demand_factors = {
            "Scenario 1": {"current": 10.0, "new": 18.0},
            "Scenario 2": {"current": 12.0, "new": 20.0},
            "Scenario 3": {"current": 13.5, "new": 22.5},
            "Scenario 4": {"current": 16.0, "new": 27.0},
            "Scenario 5": {"current": 18.0, "new": 30.0},
            "Moderate": {"current": 14.71, "new": 25.115}
        }

        self.selected_demand_level = StringVar(value="Moderate")

        # Predefined reactor types and capacities
        # Initialize predefined reactor types and capacities
        self.reactor_types = ["XE-100", "Natrium", "KP-FHR", "Em2", "Holtec SMR160", "Aurora", "VOYGR"]
        self.capacities_mw = [80, 345, 140, 265, 160, 75, 77]  # Capacities in MW

        self.reactor_type_to_category = {
            "XE-100": "High-Temperature Gas-Cooled Reactor",
            "Natrium": "Sodium-Cooled Fast Reactor",
            "KP-FHR": "Fluoride-Salt-Cooled High-Temperature Reactor",
            "Em2": "Gas-Cooled Fast Reactor",
            "Holtec SMR160": "Pressurized Water Reactor",
            "Aurora": "Fast Microreactor",
            "VOYGR": "Light Water Reactor"
        }

        self.predefined_categories = [
            "High-Temperature Gas-Cooled Reactor",
            "Sodium-Cooled Fast Reactor",
            "Fluoride-Salt-Cooled High-Temperature Reactor",
            "Gas-Cooled Fast Reactor",
            "Pressurized Water Reactor",
            "Fast Microreactor",
            "Light Water Reactor"
        ]

        # Initialize instance variables for user-added data
        self.reactors = []
        self.growth_functions = []

        # Initialize instance variables for widgets
        self.reactor_selection_var = StringVar(value="predefined")
        self.reactor_type_var = StringVar()
        self.capacity_var = StringVar()
        self.growth_rate_var = StringVar()
        self.package_var = IntVar()
        self.total_capacity_goal_var = IntVar(value=90000)
        self.capacity_distribution_var = StringVar()
        self.coefficient_variation_var = DoubleVar(value=0.2)
        self.specific_years_var = StringVar()
        self.growth_function_var = StringVar()
        self.num_simulations_var = IntVar(value=1000)
        self.current_total_capacities = []
        self.future_capacities_cum = {}  # Initialize as an empty dictionary
        self.job_breakdown = {}  # Initialize job breakdown
        self.capacities_loaded = False  # Add this line to initialize the flag

        # Placeholder for reactor data and simulation goals
        self.reactors = []
        self.growth_functions = []  # New list for storing growth functions

        # Reactor List Frame
        self.setup_list_frame()
        # Setup frames
        self.setup_reactor_frame()
        self.setup_goals_frame()
        self.setup_current_reactors_frame()

        # Configure grid resizing for the root
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)  # Configure a second column
        self.root.rowconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        self.root.rowconfigure(2, weight=1)

        # Position the frames
        self.reactor_frame.grid(row=0, column=0, padx=20, pady=5, sticky="nsew")
        self.list_frame.grid(row=1, column=0, padx=20, pady=5, sticky="nsew")
        self.goals_frame.grid(row=2, column=0, padx=20, pady=5, sticky="nsew")
        self.current_reactors_frame.grid(row=0, column=1, rowspan=3, padx=20, pady=5, sticky="nsew")

        self.extension_applied = False  # Track if an extension has been applied
        self.total_reactors_loaded = IntVar(value=0)
        self.reactors_extended = IntVar(value=0)

    def show_wait_message(self):
        self.wait_window = tk.Toplevel(self.root)
        self.wait_window.title("Please Wait")
        self.wait_window.geometry("200x100")
        tk.Label(self.wait_window, text="Please wait...").pack(expand=True)
        self.wait_window.transient(self.root)
        self.wait_window.grab_set()
        self.root.wait_window(self.wait_window)

    def hide_wait_message(self):
        if self.wait_window:
            self.wait_window.destroy()
            self.wait_window = None

    def toggle_extension_entry(self):
        if self.license_extension_var.get() == "custom":
            self.custom_extension_entry.config(state="normal")
        else:
            self.custom_extension_entry.config(state="disabled")

    def save_job_breakdown(self, job_breakdown):
        self.job_breakdown = job_breakdown
        self.plot_job_breakdown_needs()

    def open_breakdown_jobs_window(self):
        BreakdownJobsPopup(self.root, self.save_job_breakdown)

    def setup_current_reactors_frame(self):
        self.current_reactors_frame = ttk.Frame(self.root, padding="10")
        self.current_reactors_frame.grid(row=1, column=1, rowspan=3, padx=15, pady=5, sticky="nsew")

        for i in range(4):
            self.current_reactors_frame.columnconfigure(i, weight=1)
        self.current_reactors_frame.rowconfigure(20, weight=1)

        # --- File selection and license extension section ---
        ttk.Label(self.current_reactors_frame, text="Current Reactors Excel File:").grid(
            column=0, row=0, columnspan=4, padx=5, pady=5, sticky="nsew"
        )
        self.current_reactors_path_var = StringVar()
        self.current_reactors_path_entry = ttk.Entry(
            self.current_reactors_frame, width=50, textvariable=self.current_reactors_path_var
        )
        self.current_reactors_path_entry.grid(column=0, row=1, columnspan=3, padx=5, pady=5, sticky="nsew")
        self.browse_button = ttk.Button(
            self.current_reactors_frame, text="Browse", command=self.browse_file, width=20
        )
        self.browse_button.grid(column=3, row=1, padx=5, pady=5, sticky="nsew")

        ttk.Label(self.current_reactors_frame, text="License Extension Options:").grid(
            column=0, row=2, columnspan=4, padx=5, pady=(10, 5), sticky="nsew"
        )
        extension_frame = ttk.Frame(self.current_reactors_frame)
        extension_frame.grid(column=0, row=3, columnspan=4, padx=5, pady=5, sticky="nsew")
        for i in range(4):
            extension_frame.columnconfigure(i, weight=1)

        self.license_extension_var = StringVar(value="no_renewal")

        # No Renewal option
        self.no_renewal_radio = ttk.Radiobutton(
            extension_frame, text="No Renewal", variable=self.license_extension_var,
            value="no_renewal", command=self.toggle_extension_entry
        )
        self.no_renewal_radio.grid(column=0, row=0, padx=5, pady=5, sticky="nsew")

        # Custom Extension option
        self.custom_year_radio = ttk.Radiobutton(
            extension_frame, text="Custom Years", variable=self.license_extension_var,
            value="custom", command=self.toggle_extension_entry
        )
        self.custom_year_radio.grid(column=1, row=0, padx=5, pady=5, sticky="nsew")

        # Entry field for custom years
        ttk.Label(extension_frame, text="Number of Years to Extend:").grid(column=2, row=0, padx=5, pady=5, sticky="nsew")
        self.custom_extension_years = IntVar(value=80)
        self.custom_extension_entry = ttk.Entry(extension_frame, width=10, textvariable=self.custom_extension_years)
        self.custom_extension_entry.grid(column=3, row=0, padx=5, pady=5, sticky="nsew")
        self.custom_extension_entry.config(state="disabled")  # disabled by default

        # --- Extend Percentage of Eligible Reactors ---
        ttk.Label(self.current_reactors_frame, text="Extend Percentage of Eligible Reactors:").grid(
            column=0, row=5, padx=5, pady=5, sticky="nsew"
        )
        self.extension_percentage_var = DoubleVar(value=100)
        self.extension_percentage_entry = ttk.Entry(
            self.current_reactors_frame, width=10, textvariable=self.extension_percentage_var
        )
        self.extension_percentage_entry.grid(column=1, row=5, padx=5, pady=5, sticky="nsew")

        # --- Buttons ---
        button_frame = ttk.Frame(self.current_reactors_frame)
        button_frame.grid(column=0, row=6, columnspan=4, padx=10, pady=10, sticky="nsew")
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        self.apply_license_extension_button = ttk.Button(
            button_frame, text="Apply License Extension", command=self.handle_selection, width=30
        )
        self.apply_license_extension_button.grid(column=0, row=0, padx=10, pady=10, sticky="nsew")
        self.calculate_capacity_button = ttk.Button(
            button_frame, text="Calculate and Load Current Reactor Capacities",
            command=self.trigger_capacity_calculation, width=40
        )
        self.calculate_capacity_button.grid(column=1, row=0, padx=10, pady=10, sticky="nsew")

        # --- Reactor Info Frame ---
        reactor_info_frame = ttk.LabelFrame(
            self.current_reactors_frame, text="Current Reactor Count", padding=(10, 10)
        )
        reactor_info_frame.grid(column=0, row=7, columnspan=4, padx=5, pady=5, sticky="nsew")
        ttk.Label(reactor_info_frame, text="Current Reactors:").grid(column=0, row=0, padx=5, pady=5, sticky="nsew")
        self.total_reactors_label = ttk.Label(reactor_info_frame, text="0")
        self.total_reactors_label.grid(column=1, row=0, padx=5, pady=5, sticky="nsew")
        ttk.Label(reactor_info_frame, text="Current Reactors with Extended Licenses:").grid(
            column=2, row=0, padx=5, pady=5, sticky="nsew"
        )
        self.extended_reactors_label = ttk.Label(reactor_info_frame, text="0")
        self.extended_reactors_label.grid(column=3, row=0, padx=5, pady=5, sticky="nsew")

        # --- Capacity Display ---
        ttk.Label(self.current_reactors_frame, text="Current Reactors Capacity:", font=("Arial", 10, "bold")).grid(
            column=0, row=8, columnspan=4, padx=5, pady=5, sticky="nsew"
        )
        self.results_text = tk.Text(self.current_reactors_frame, height=10, width=20)
        self.results_text.grid(row=9, column=0, columnspan=4, padx=5, pady=5, sticky="nsew")
        self.results_text.config(state='disabled')
        self.scrollbar = ttk.Scrollbar(self.current_reactors_frame, command=self.results_text.yview)
        self.scrollbar.grid(row=9, column=4, sticky='nsew')
        self.results_text['yscrollcommand'] = self.scrollbar.set

        # --- Plot Buttons ---
        plot_button_frame = ttk.Frame(self.current_reactors_frame)
        plot_button_frame.grid(column=0, row=10, columnspan=4, padx=5, pady=10, sticky="nsew")
        for i in range(3):
            plot_button_frame.columnconfigure(i, weight=1)
        self.plot_current_capacity_button = ttk.Button(
            plot_button_frame, text="Plot Current Reactor Capacity", command=self.plot_current_capacity
        )
        self.plot_current_capacity_button.grid(column=0, row=0, padx=5, pady=5, sticky="nsew")
        self.plot_total_projection_button = ttk.Button(
            plot_button_frame, text="Plot Total Capacity Projection", command=self.plot_total_projection
        )
        self.plot_total_projection_button.grid(column=1, row=0, padx=5, pady=5, sticky="nsew")

        style = ttk.Style()
        style.configure("FuelDemand.TButton", font=("Helvetica", 10, "bold"), foreground="blue", padding=6)
        self.fuel_cycle_button = ttk.Button(
            plot_button_frame, text="Fuel Cycle Demand >", command=self.open_fuel_cycle_window,
            style="FuelDemand.TButton"
        )
        self.fuel_cycle_button.grid(column=2, row=0, padx=5, pady=5, sticky="nsew")

        # --- Workforce Factors Section (Current Workforce) ---
        ttk.Label(self.current_reactors_frame, text="Current Reactor Workforce Factors").grid(
            column=0, row=11, columnspan=4, padx=5, pady=5, sticky="nsew"
        )
        ttk.Label(self.current_reactors_frame, text="Current Workforce Distribution:").grid(
            column=0, row=12, padx=5, pady=5, sticky="nsew"
        )
        self.current_workforce_dist_var = StringVar(value="Uniform")
        self.current_workforce_dist_combobox = ttk.Combobox(
            self.current_reactors_frame, textvariable=self.current_workforce_dist_var,
            values=["Uniform", "Normal"], state="readonly", width=15
        )
        self.current_workforce_dist_combobox.grid(column=1, row=12, padx=5, pady=5, sticky="nsew")
        self.current_workforce_dist_combobox.bind("<<ComboboxSelected>>", self.on_current_workforce_dist_change)

        # Uniform fields for current workforce (initially visible)
        self.current_workforce_uniform_lower_label = ttk.Label(self.current_reactors_frame, text="Low (jobs/GW):")
        self.current_workforce_uniform_lower_label.grid(column=0, row=13, padx=5, pady=5, sticky="nsew")
        self.current_workforce_uniform_lower_var = DoubleVar(value=200)
        self.current_workforce_uniform_lower_entry = ttk.Entry(self.current_reactors_frame, width=10,
                                                               textvariable=self.current_workforce_uniform_lower_var)
        self.current_workforce_uniform_lower_entry.grid(column=1, row=13, padx=5, pady=5, sticky="nsew")
        self.current_workforce_uniform_upper_label = ttk.Label(self.current_reactors_frame, text="High (jobs/GW):")
        self.current_workforce_uniform_upper_label.grid(column=2, row=13, padx=5, pady=5, sticky="nsew")
        self.current_workforce_uniform_upper_var = DoubleVar(value=300)
        self.current_workforce_uniform_upper_entry = ttk.Entry(self.current_reactors_frame, width=10,
                                                               textvariable=self.current_workforce_uniform_upper_var)
        self.current_workforce_uniform_upper_entry.grid(column=3, row=13, padx=5, pady=5, sticky="ew")

        # Normal fields for current workforce (initially hidden)
        self.current_workforce_normal_mean_label = ttk.Label(self.current_reactors_frame, text="Mean (jobs/GW):")
        self.current_workforce_normal_mean_entry = ttk.Entry(self.current_reactors_frame, width=10)
        self.current_workforce_normal_cv_label = ttk.Label(self.current_reactors_frame, text="Coef. Variation:")
        self.current_workforce_normal_cv_entry = ttk.Entry(self.current_reactors_frame, width=10)
        self.current_workforce_normal_mean_label.grid_remove()
        self.current_workforce_normal_mean_entry.grid_remove()
        self.current_workforce_normal_cv_label.grid_remove()
        self.current_workforce_normal_cv_entry.grid_remove()

        # --- Workforce Factors Section (Future Workforce) ---
        ttk.Label(self.current_reactors_frame, text="Future Reactor Workforce Factors").grid(
            column=0, row=14, columnspan=4, padx=5, pady=5, sticky="nsew"
        )
        ttk.Label(self.current_reactors_frame, text="Future Workforce Distribution:").grid(
            column=0, row=15, padx=5, pady=5, sticky="nsew"
        )
        self.future_workforce_dist_var = StringVar(value="Uniform")
        self.future_workforce_dist_combobox = ttk.Combobox(
            self.current_reactors_frame, textvariable=self.future_workforce_dist_var,
            values=["Uniform", "Normal"], state="readonly", width=15
        )
        self.future_workforce_dist_combobox.grid(column=1, row=15, padx=5, pady=5, sticky="nsew")
        self.future_workforce_dist_combobox.bind("<<ComboboxSelected>>", self.on_future_workforce_dist_change)

        # Uniform fields for future workforce
        self.future_workforce_uniform_lower_label = ttk.Label(self.current_reactors_frame, text="Low (jobs/GW):")
        self.future_workforce_uniform_lower_label.grid(column=0, row=16, padx=5, pady=5, sticky="nsew")
        self.future_workforce_uniform_lower_var = DoubleVar(value=200)
        self.future_workforce_uniform_lower_entry = ttk.Entry(self.current_reactors_frame, width=10,
                                                              textvariable=self.future_workforce_uniform_lower_var)
        self.future_workforce_uniform_lower_entry.grid(column=1, row=16, padx=5, pady=5, sticky="nsew")
        self.future_workforce_uniform_upper_label = ttk.Label(self.current_reactors_frame, text="High (jobs/GW):")
        self.future_workforce_uniform_upper_label.grid(column=2, row=16, padx=5, pady=5, sticky="nsew")
        self.future_workforce_uniform_upper_var = DoubleVar(value=300)
        self.future_workforce_uniform_upper_entry = ttk.Entry(self.current_reactors_frame, width=10,
                                                              textvariable=self.future_workforce_uniform_upper_var)
        self.future_workforce_uniform_upper_entry.grid(column=3, row=16, padx=5, pady=5, sticky="ew")

        # Normal fields for future workforce (initially hidden)
        self.future_workforce_normal_mean_label = ttk.Label(self.current_reactors_frame, text="Mean (jobs/GW):")
        self.future_workforce_normal_mean_entry = ttk.Entry(self.current_reactors_frame, width=10)
        self.future_workforce_normal_cv_label = ttk.Label(self.current_reactors_frame, text="Coef. Variation:")
        self.future_workforce_normal_cv_entry = ttk.Entry(self.current_reactors_frame, width=10)
        self.future_workforce_normal_mean_label.grid_remove()
        self.future_workforce_normal_mean_entry.grid_remove()
        self.future_workforce_normal_cv_label.grid_remove()
        self.future_workforce_normal_cv_entry.grid_remove()

        # --- Job Demand Buttons Section ---
        workforce_button_frame = ttk.Frame(self.current_reactors_frame)
        workforce_button_frame.grid(column=0, row=17, columnspan=4, padx=5, pady=10, sticky="nsew")
        workforce_button_frame.columnconfigure(0, weight=1)
        workforce_button_frame.columnconfigure(1, weight=1)
        self.plot_workforce_needs_button = ttk.Button(
            workforce_button_frame, text="Calculate Job Needs", command=self.plot_workforce_needs
        )
        self.plot_workforce_needs_button.grid(column=0, row=0, padx=5, pady=5, sticky="nsew")
        # Define a new style for the Breakdown Jobs button
        style = ttk.Style()
        style.configure("JobBreakdown.TButton",
                        font=("Helvetica", 10, "bold"),
                        foreground="blue",
                        padding=6)

        # Create the button with the new style and update its text to include an arrow.
        self.breakdown_jobs_button = ttk.Button(
            workforce_button_frame,
            text="Break Down Jobs >",
            command=self.open_breakdown_jobs_window,
            style="JobBreakdown.TButton"
        )
        self.breakdown_jobs_button.grid(column=1, row=0, padx=5, pady=5, sticky="nsew")

    def open_fuel_cycle_window(self):
        FuelCycleWindow(
            self.root,
            self.selected_demand_level,
            self.current_total_capacities,
            getattr(self, 'future_capacities_cum', {}),  # default to empty dict
            self.num_simulations_var.get(),
            getattr(self, 'future_capacity_by_type_cumulative', {})  # default to empty dict
        )

    # <-- pass number of simulations

    def on_current_workforce_dist_change(self, event=None):
        dist = self.current_workforce_dist_var.get()
        if dist == "Uniform":
            # Show uniform fields; hide normal fields.
            self.current_workforce_uniform_lower_label.grid()
            self.current_workforce_uniform_lower_entry.grid()
            self.current_workforce_uniform_upper_label.grid()
            self.current_workforce_uniform_upper_entry.grid()
            self.current_workforce_normal_mean_label.grid_remove()
            self.current_workforce_normal_mean_entry.grid_remove()
            self.current_workforce_normal_cv_label.grid_remove()
            self.current_workforce_normal_cv_entry.grid_remove()
        elif dist == "Normal":
            # Hide uniform fields; show normal fields.
            self.current_workforce_uniform_lower_label.grid_remove()
            self.current_workforce_uniform_lower_entry.grid_remove()
            self.current_workforce_uniform_upper_label.grid_remove()
            self.current_workforce_uniform_upper_entry.grid_remove()
            # Place normal fields in the same grid row (row 13)
            self.current_workforce_normal_mean_label.grid(column=0, row=13, padx=5, pady=5, sticky="nsew")
            self.current_workforce_normal_mean_entry.grid(column=1, row=13, padx=5, pady=5, sticky="nsew")
            self.current_workforce_normal_cv_label.grid(column=2, row=13, padx=5, pady=5, sticky="nsew")
            self.current_workforce_normal_cv_entry.grid(column=3, row=13, padx=5, pady=5, sticky="nsew")

    def on_future_workforce_dist_change(self, event=None):
        dist = self.future_workforce_dist_var.get()
        if dist == "Uniform":
            self.future_workforce_uniform_lower_label.grid()
            self.future_workforce_uniform_lower_entry.grid()
            self.future_workforce_uniform_upper_label.grid()
            self.future_workforce_uniform_upper_entry.grid()
            self.future_workforce_normal_mean_label.grid_remove()
            self.future_workforce_normal_mean_entry.grid_remove()
            self.future_workforce_normal_cv_label.grid_remove()
            self.future_workforce_normal_cv_entry.grid_remove()
        elif dist == "Normal":
            self.future_workforce_uniform_lower_label.grid_remove()
            self.future_workforce_uniform_lower_entry.grid_remove()
            self.future_workforce_uniform_upper_label.grid_remove()
            self.future_workforce_uniform_upper_entry.grid_remove()
            self.future_workforce_normal_mean_label.grid(column=0, row=16, padx=5, pady=5, sticky="nsew")
            self.future_workforce_normal_mean_entry.grid(column=1, row=16, padx=5, pady=5, sticky="nsew")
            self.future_workforce_normal_cv_label.grid(column=2, row=16, padx=5, pady=5, sticky="nsew")
            self.future_workforce_normal_cv_entry.grid(column=3, row=16, padx=5, pady=5, sticky="nsew")

    # Method to clear the file path
    def clear_file(self):
        self.current_reactors_path_var.set('')
        self.results_text.config(state='normal')
        self.results_text.delete('1.0', tk.END)
        self.results_text.config(state='disabled')
        self.capacities_loaded = False
        self.calculate_capacity_button.config(state='normal')

    def plot_current_capacity(self):
        if not self.current_total_capacities:
            messagebox.showerror("Error", "Please load current reactor capacities before plotting.")
            return

        years = [2025, 2030, 2035, 2040, 2045, 2050]
        capacities = [float(cap.split(': ')[1].split(' MW')[0]) for cap in self.current_total_capacities]

        # Plotting the capacities using scatter plot and connect them with a line
        plt.figure(figsize=(10, 6))  # Decrease figure size
        plt.scatter(years, capacities, color='blue')  # Plot scatter points
        plt.plot(years, capacities, color='blue')  # Connect points with a line
        plt.xlabel('Year', fontsize=16)  # Set larger font size for x-axis label
        plt.ylabel('Total Capacity (MW)', fontsize=16)  # Set larger font size for y-axis label
        plt.title('Current Reactor Capacities Over Time', fontsize=18)  # Increase title font size
        plt.grid(True)

        # Set larger font size for tick labels
        plt.tick_params(axis='both', which='major', labelsize=14)

        plt.show()

    def clear_all_data(self):
        """
        Clear all user-inputted data, including added reactors, growth rates, capacities, and current reactor data.
        Does not modify visibility settings or predefined reactors.
        """
        if messagebox.askyesno("Confirm Clear",
                               "Are you sure you want to clear all simulation data? All data will be lost."):
            # Clear only the user-added reactors and related data
            self.reactors.clear()  # Clear the user-added reactors list
            self.growth_functions.clear()  # Clear the growth functions list (user-added growth functions)
            self.current_total_capacities.clear()  # Clear current capacities list
            self.future_capacities_cum.clear()  # Clear future capacities dictionary
            self.job_breakdown.clear()  # Clear job breakdown data

            # Clear input fields (reset values)
            self.mean_growth_rate_var.set(0.2)  # Reset mean growth rate to default
            self.cov_growth_rate_var.set(0.1)  # Reset CoV to default
            self.reactor_growth_function_combobox.current(0)  # Reset growth function to default (Exponential)
            self.capacity_var.set('')  # Clear the capacity input
            self.package_var.set(1)  # Reset number of units (Package) to 1
            self.total_capacity_goal_var.set(90000)  # Reset total capacity goal to default
            self.growth_rate_distribution_combobox.current(0)  # Reset Growth Rate Distribution to 'Normal'

            # Reset options for loading the current reactors
            self.current_reactors_path_var.set('')  # Clear the file path for current reactors
            self.capacities_loaded = False  # Set capacities_loaded flag to False
            self.calculate_capacity_button.config(
                state='normal')  # Re-enable the "Calculate and Load" button if it was disabled
            self.results_text.config(state='normal')  # Clear text box for results
            self.results_text.delete('1.0', tk.END)
            self.results_text.config(state='disabled')

            # Clear the Treeview widget (user-added reactors should be here)
            self.reactor_table.delete(*self.reactor_table.get_children())  # Clear all items from the Treeview

            # Reset the new workforce distribution fields
            self.current_workforce_dist_var.set("Uniform")
            self.current_workforce_uniform_lower_var.set(200)
            self.current_workforce_uniform_upper_var.set(300)
            self.future_workforce_dist_var.set("Uniform")
            self.future_workforce_uniform_lower_var.set(200)
            self.future_workforce_uniform_upper_var.set(300)
            self.current_workforce_normal_mean_entry.delete(0, tk.END)
            self.current_workforce_normal_cv_entry.delete(0, tk.END)
            self.future_workforce_normal_mean_entry.delete(0, tk.END)
            self.future_workforce_normal_cv_entry.delete(0, tk.END)

            # Update total reactor and extended reactors labels
            self.total_reactors_label.config(text="0")  # Reset total reactors count
            self.extended_reactors_label.config(text="0")  # Reset extended reactors count
            # --- Reset Current Reactor Calculations ---
            self.current_reactors_path_var.set("")  # Clear file path
            self.capacities_loaded = False  # Allow loading again
            self.extension_applied = False  # Allow extension again

            self.total_reactors_label.config(text="0")  # Reset display labels
            self.extended_reactors_label.config(text="0")

            self.total_reactors_loaded.set(0)
            self.reactors_extended.set(0)

            # Re-enable Load Capacities button
            self.calculate_capacity_button.config(state="normal")

            # Clear results display
            self.results_text.config(state='normal')
            self.results_text.delete('1.0', tk.END)
            self.results_text.config(state='disabled')

            # --- Reset Current Reactor Calculations ---
            self.current_reactors_path_var.set("")  # Clear file path
            self.capacities_loaded = False  # Allow loading again
            self.extension_applied = False  # Allow extension again

            self.total_reactors_label.config(text="0")  # Reset display labels
            self.extended_reactors_label.config(text="0")

            self.total_reactors_loaded.set(0)
            self.reactors_extended.set(0)

            # Re-enable Load Capacities button
            self.calculate_capacity_button.config(state="normal")

            # Clear results display
            self.results_text.config(state='normal')
            self.results_text.delete('1.0', tk.END)
            self.results_text.config(state='disabled')

            # Show a confirmation message
            messagebox.showinfo("Data Cleared",
                                "All simulation data, including current reactor data, has been cleared.")

    def plot_job_breakdown_needs(self):
        if not self.current_total_capacities:
            messagebox.showerror("Error", "Please load current reactor capacities before plotting job breakdown needs.")
            return

        if not self.future_capacities_cum:
            messagebox.showerror("Error", "Please simulate future capacities before plotting job breakdown needs.")
            return

        # Combine capacities
        combined_capacities = self.combine_current_and_future_capacities(
            self.current_total_capacities,
            self.future_capacities_cum
        )

        # Create structure for job needs
        job_needs_by_category = {category: [] for category in self.job_breakdown.keys()}

        # Compute workforce needs
        workforce_needs = self.calculate_workforce_needs(combined_capacities)

        # Populate job needs per category
        for scenario, job_needs in workforce_needs.items():
            for year_index, total_jobs in enumerate(job_needs):
                for category, percentage in self.job_breakdown.items():
                    job_needs_by_category[category].append(total_jobs * (percentage / 100))

        # Prepare data for plotting
        years = [2025, 2030, 2035, 2040, 2045, 2050]
        data_for_plot = []

        num_years = len(years)
        num_scenarios = len(workforce_needs)

        for year_index, year in enumerate(years):
            for category in self.job_breakdown.keys():
                # Extract all scenario data for this category and year
                job_needs = [
                    job_needs_by_category[category][i]
                    for i in range(year_index, num_scenarios * num_years, num_years)
                ]
                for j in job_needs:
                    data_for_plot.append((year, category, j))

        df = pd.DataFrame(data_for_plot, columns=['Year', 'Category', 'Job Needs'])

        # Sort categories by highest % first
        categories = sorted(self.job_breakdown.keys(), key=lambda c: self.job_breakdown[c], reverse=True)

        num_categories = len(categories)
        plots_per_figure = 6
        num_figures = (num_categories + plots_per_figure - 1) // plots_per_figure

        for fig_idx in range(num_figures):

            # -----------------------------
            # Determine y-axis max for this figure only
            # -----------------------------
            max_value_for_fig = 0
            start_idx = fig_idx * plots_per_figure
            end_idx = min(start_idx + plots_per_figure, num_categories)

            for category_idx in range(start_idx, end_idx):
                category = categories[category_idx]
                cat_vals = df[df['Category'] == category]["Job Needs"]
                if not cat_vals.empty:
                    max_value_for_fig = max(max_value_for_fig, cat_vals.max())

            # -----------------------------
            # Create the figure layout
            # -----------------------------
            fig, axes = plt.subplots(nrows=2, ncols=3, figsize=(15, 10))
            axes = axes.flatten()

            for subplot_idx in range(plots_per_figure):
                category_idx = start_idx + subplot_idx
                if category_idx < num_categories:
                    category = categories[category_idx]
                    ax = axes[subplot_idx]

                    category_data = df[df['Category'] == category]

                    # Extract job needs grouped by year
                    data_by_year = [
                        category_data[category_data['Year'] == year]["Job Needs"].tolist()
                        for year in years
                    ]

                    # Draw boxplot
                    box = ax.boxplot(
                        data_by_year,
                        labels=years,
                        patch_artist=True,
                        showmeans=True,
                        meanline=True
                    )

                    # Set consistent Y scale within this figure
                    ax.set_ylim(0, max_value_for_fig)

                    # Color palette
                    colors = sns.color_palette("husl", len(years))
                    for patch, color in zip(box['boxes'], colors):
                        patch.set_facecolor(color)

                    # Mean markers
                    for mean in box['means']:
                        mean.set(marker='o', color='red', markersize=6)

                    # Titles and labels
                    ax.set_title(category, fontsize=10)
                    ax.set_xlabel("Year", fontsize=9)
                    ax.set_ylabel("Job Needs", fontsize=9)
                    ax.grid(True)
                    ax.tick_params(axis='both', which='major', labelsize=8)

                else:
                    # Remove unused subplots
                    fig.delaxes(axes[subplot_idx])

            plt.tight_layout()
            plt.subplots_adjust(top=0.88)
            fig.suptitle(f"Job Needs Breakdown Across All Simulations - Part {fig_idx + 1}", fontsize=12)
            plt.show()

    def calculate_workforce_needs(self, combined_capacities):
        workforce_needs = {}
        scenario_keys = list(combined_capacities.keys())

        # --- Sample once per scenario ---
        if self.current_workforce_dist_var.get() == "Uniform":
            low_current = self.current_workforce_uniform_lower_var.get()
            high_current = self.current_workforce_uniform_upper_var.get()
            current_samples = {
                scenario: np.random.uniform(low=low_current, high=high_current)
                for scenario in scenario_keys
            }
        elif self.current_workforce_dist_var.get() == "Normal":
            try:
                mean_current = float(self.current_workforce_normal_mean_entry.get())
                cv_current = float(self.current_workforce_normal_cv_entry.get())
            except Exception:
                mean_current = 200
                cv_current = 0.1
            std_current = mean_current * cv_current
            current_samples = {
                scenario: np.random.normal(loc=mean_current, scale=std_current)
                for scenario in scenario_keys
            }
        else:
            current_samples = {scenario: 0 for scenario in scenario_keys}

        if self.future_workforce_dist_var.get() == "Uniform":
            low_future = self.future_workforce_uniform_lower_var.get()
            high_future = self.future_workforce_uniform_upper_var.get()
            future_samples = {
                scenario: np.random.uniform(low=low_future, high=high_future)
                for scenario in scenario_keys
            }
        elif self.future_workforce_dist_var.get() == "Normal":
            try:
                mean_future = float(self.future_workforce_normal_mean_entry.get())
                cv_future = float(self.future_workforce_normal_cv_entry.get())
            except Exception:
                mean_future = 200
                cv_future = 0.1
            std_future = mean_future * cv_future
            future_samples = {
                scenario: np.random.normal(loc=mean_future, scale=std_future)
                for scenario in scenario_keys
            }
        else:
            future_samples = {scenario: 0 for scenario in scenario_keys}

        # --- Compute job needs using the same sample for each year ---
        for scenario, capacities in combined_capacities.items():
            workforce_needs[scenario] = []
            sample_current = current_samples[scenario]
            sample_future = future_samples[scenario]

            for i, capacity in enumerate(capacities):
                if i < len(self.current_total_capacities):
                    try:
                        current_capacity = float(self.current_total_capacities[i].split(": ")[1].split(" ")[0])
                    except Exception:
                        current_capacity = 0
                else:
                    current_capacity = 0

                future_capacity = capacity - current_capacity

                workforce_need_current = (current_capacity / 1000) * sample_current
                workforce_need_future = (future_capacity / 1000) * sample_future
                total_workforce_need = workforce_need_current + workforce_need_future

                workforce_needs[scenario].append(total_workforce_need)

        return workforce_needs

    def capacity_breakdown(self):
        # Check if the deployments_per_type dictionary is populated
        if not hasattr(self, 'deployments_per_type') or not self.deployments_per_type:
            messagebox.showerror("Error", "No deployment data available. Please run the simulation first.")
            return

        # Prepare data for plotting
        data_for_plot = []
        reactor_types = list(self.deployments_per_type.keys())

        # Collect the data for each reactor type
        for reactor_type in reactor_types:
            percentages = self.deployments_per_type[reactor_type]
            for percentage in percentages:
                data_for_plot.append((reactor_type, percentage))

        # Convert data to a DataFrame for seaborn plotting
        df = pd.DataFrame(data_for_plot, columns=['Reactor Identifier', 'Capacity Percentage'])

        # Plot a violin plot for each reactor type with a smaller figure size
        plt.figure(figsize=(10, 6))  # Decrease figure size
        sns.violinplot(x='Reactor Identifier', y='Capacity Percentage', data=df, palette='Set2', inner='quartile')

        # Larger font sizes for labels and ticks
        plt.title('Reactor Identifier Capacity Percentage Across Simulations', fontsize=20)
        plt.xlabel('Reactor Identifier', fontsize=18)
        plt.ylabel('Capacity Percentage', fontsize=18)
        plt.grid(True)

        # Increase the font size of the tick labels
        plt.tick_params(axis='both', which='major', labelsize=16)

        plt.show()

    def plot_workforce_needs(self):
        if not self.current_total_capacities:
            messagebox.showerror("Error", "Please load current reactor capacities before plotting workforce needs.")
            return

        if not self.future_capacities_cum:
            messagebox.showerror("Error", "Please simulate future capacities before plotting workforce needs.")
            return

        combined_capacities = self.combine_current_and_future_capacities(self.current_total_capacities,
                                                                         self.future_capacities_cum)

        workforce_needs = {}

        scenario_keys = list(combined_capacities.keys())

        # Generate one sample per scenario
        if self.current_workforce_dist_var.get() == "Uniform":
            low_val = self.current_workforce_uniform_lower_var.get()
            high_val = self.current_workforce_uniform_upper_var.get()
            workforce_samples_current = {scenario: np.random.uniform(low_val, high_val) for scenario in scenario_keys}
        elif self.current_workforce_dist_var.get() == "Normal":
            try:
                mean_current = float(self.current_workforce_normal_mean_entry.get())
                cv_current = float(self.current_workforce_normal_cv_entry.get())
            except Exception:
                mean_current = 200
                cv_current = 0.1
            std_current = mean_current * cv_current
            workforce_samples_current = {scenario: np.random.normal(mean_current, std_current) for scenario in
                                         scenario_keys}
        else:
            workforce_samples_current = {scenario: 0 for scenario in scenario_keys}

        if self.future_workforce_dist_var.get() == "Uniform":
            low_val = self.future_workforce_uniform_lower_var.get()
            high_val = self.future_workforce_uniform_upper_var.get()
            workforce_samples_future = {scenario: np.random.uniform(low_val, high_val) for scenario in scenario_keys}
        elif self.future_workforce_dist_var.get() == "Normal":
            try:
                mean_future = float(self.future_workforce_normal_mean_entry.get())
                cv_future = float(self.future_workforce_normal_cv_entry.get())
            except Exception:
                mean_future = 200
                cv_future = 0.1
            std_future = mean_future * cv_future
            workforce_samples_future = {scenario: np.random.normal(mean_future, std_future) for scenario in
                                        scenario_keys}
        else:
            workforce_samples_future = {scenario: 0 for scenario in scenario_keys}

        for scenario in scenario_keys:
            capacities = combined_capacities[scenario]
            workforce_needs[scenario] = []
            for i, capacity in enumerate(capacities):
                if i < len(self.current_total_capacities):
                    try:
                        current_capacity = float(self.current_total_capacities[i].split(": ")[1].split(" ")[0])
                    except Exception:
                        current_capacity = 0
                else:
                    current_capacity = 0

                future_capacity = capacity - current_capacity

                sample_current = workforce_samples_current[scenario]
                sample_future = workforce_samples_future[scenario]

                workforce_need_current = (current_capacity / 1000) * sample_current
                workforce_need_future = (future_capacity / 1000) * sample_future

                total_workforce_need = workforce_need_current + workforce_need_future
                workforce_needs[scenario].append(total_workforce_need)

        self.display_demand(
            workforce_needs,
            'Job Market Needs',
            'Number of Jobs',
            axis_font_size=18,
            tick_font_size=16
        )

    def display_demand(self, demand_data, title, ylabel, axis_font_size=18, tick_font_size=16):
        plt.figure(figsize=(10, 6))  # Decrease the overall size of the plot (10x6 inches)

        # Prepare data for plotting
        years = [2025, 2030, 2035, 2040, 2045, 2050]
        data_by_year = {year: [] for year in years}

        for scenario in demand_data:
            for i, year in enumerate(years):
                data_by_year[year].append(demand_data[scenario][i])

        # Convert data to list of lists for box plot
        data_for_boxplot = [data_by_year[year] for year in years]

        # Colors for each year
        colors = ['lightblue', 'lightgreen', 'lightcoral', 'lightyellow', 'lightpink', 'lightskyblue']

        # Create the box plot
        box = plt.boxplot(data_for_boxplot, labels=years, patch_artist=True, showmeans=True, meanline=True)

        # Customize box plot colors
        for patch, color in zip(box['boxes'], colors):
            patch.set_facecolor(color)

        # Customize mean markers
        for mean in box['means']:
            mean.set(marker='o', color='red', markersize=6)

        # Set title, axis labels, and grid with larger font sizes
        plt.title(title, fontsize=axis_font_size + 4)  # Larger title font size
        plt.xlabel('Year', fontsize=axis_font_size)  # Set larger font size for x-axis label
        plt.ylabel(ylabel, fontsize=axis_font_size)  # Set larger font size for y-axis label
        plt.grid(True)

        # Set larger font size for tick labels
        plt.tick_params(axis='both', which='major', labelsize=tick_font_size)

        plt.show()

    def combine_current_and_future_capacities(self, current_capacities, future_capacities):
        """
        Combines current reactor capacities with projected future capacities for each scenario.

        Parameters:
        - current_capacities (list): List of current capacities from specific years, formatted as "Year XXXX: YYYYY MW".
        - future_capacities (dict): Dictionary of future capacities with scenario as keys and list of capacities as values.

        Returns:
        - dict: A dictionary with keys as scenario indices and values as lists of total capacities
                for each year combining both current and future capacities.
        """
        combined_capacities = {}

        # Parse out the numeric values from the current capacities list
        current_cap_floats = [float(cap.split(': ')[1].split(' MW')[0]) for cap in current_capacities]

        for scenario, future_cap_list in future_capacities.items():
            if len(current_cap_floats) != len(future_cap_list):
                raise ValueError(
                    "The number of years in current capacities does not match the future capacities for scenario: " + scenario)

            # Combine the capacities year by year
            combined_capacities[scenario] = [
                current + future
                for current, future in zip(current_cap_floats, future_cap_list)
            ]

        return combined_capacities

    def trigger_capacity_calculation(self):
        file_path = self.current_reactors_path_var.get()
        if file_path:
            try:
                # Load the Excel file
                df = pd.read_excel(file_path)

                # Ensure the necessary columns are present
                required_columns = ['Operating License', 'Expiration License', 'Capacity MWe']
                missing_columns = [col for col in required_columns if col not in df.columns]

                if missing_columns:
                    missing_columns_str = ", ".join(missing_columns)
                    messagebox.showerror("Missing Columns",
                                         f"The following required columns are missing in the selected file: {missing_columns_str}. "
                                         "Please select a valid file.")
                    return

                # Convert dates
                df['Operating License'] = pd.to_datetime(df['Operating License'], format='%m-%Y')
                df['Expiration License'] = pd.to_datetime(df['Expiration License'], format='%m-%Y')

                specific_years = [2025, 2030, 2035, 2040, 2045, 2050]

                # Prepare data for displaying and calculating total capacities
                self.current_total_capacities.clear()  # Clear previous data
                years = []
                capacities = []

                for year in specific_years:
                    total_capacity = df[df['Expiration License'] >= pd.Timestamp(year=year, month=1, day=1)][
                        'Capacity MWe'].sum()
                    self.current_total_capacities.append(
                        f"Year {year}: {total_capacity} MW")  # Storing capacities in a class attribute
                    years.append(year)
                    capacities.append(total_capacity)

                # Display results in the Text widget
                self.results_text.config(state='normal')
                self.results_text.delete('1.0', tk.END)
                for line in self.current_total_capacities:
                    self.results_text.insert(tk.END, line + '\n')
                self.results_text.config(state='disabled')

                # Disable the button after loading capacities
                self.capacities_loaded = True
                self.calculate_capacity_button.config(state='disabled')

            except Exception as e:
                messagebox.showerror("Error", f"An error occurred while processing the file: {str(e)}")
        else:
            messagebox.showerror("Error", "No file selected. Please select a file first.")

    def update_license_expiration(self, input_file_path, extension_years):
        df = pd.read_excel(input_file_path)
        df['Operating License'] = pd.to_datetime(df['Operating License'], format='%m-%Y')
        df['Expiration License'] = pd.to_datetime(df['Expiration License'], format='%m-%Y')

        # Calculate the original license duration
        df['Original Expiration'] = df['Expiration License']
        df['License Duration'] = (df['Expiration License'] - df['Operating License']) / timedelta(days=365)

        # Apply the extension only to reactors with shorter license durations
        mask = df['License Duration'] < extension_years
        df.loc[mask, 'Expiration License'] = df.loc[mask, 'Operating License'] + pd.DateOffset(years=extension_years)

        # Count the number of reactors where the expiration date has actually been updated
        extended_reactors_count = (df['Expiration License'] > df['Original Expiration']).sum()

        # Drop the temporary columns used for calculation
        df.drop(['Original Expiration', 'License Duration'], axis=1, inplace=True)

        return df, extended_reactors_count

    def handle_selection(self):
        if self.extension_applied:
            messagebox.showwarning("Extension Already Applied", "An extension has already been applied to this file.")
            return

        file_path = self.current_reactors_path_var.get()
        if not file_path:
            messagebox.showerror("No File Selected", "Please select a file first.")
            return

        try:
            df = pd.read_excel(file_path)

            # Check if the required columns are present in the DataFrame
            required_columns = ['Operating License', 'Expiration License']
            missing_columns = [col for col in required_columns if col not in df.columns]

            if missing_columns:
                missing_columns_str = ", ".join(missing_columns)
                messagebox.showerror("Missing Columns",
                                     f"The following required columns are missing in the selected file: {missing_columns_str}. "
                                     "Please select a valid file.")
                return  # Exit the method if required columns are missing

            # Proceed with applying the extension if the columns are present
            if self.license_extension_var.get() == "no_renewal":
                extension_years = 0
            else:
                try:
                    extension_years = int(self.custom_extension_years.get())
                    if extension_years <= 0:
                        messagebox.showerror("Invalid Input", "Please enter a positive number of years for extension.")
                        return
                except Exception:
                    messagebox.showerror("Invalid Input", "Please enter a valid number of years.")
                    return
            if extension_years > 0:
                self.apply_extension(file_path, extension_years)
            else:
                # If no renewal, show a success message
                messagebox.showinfo("No Renewal Applied",
                                    "No license renewal applied. The current data remains unchanged.")
                self.extension_applied = True  # Mark that an action has been taken

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while processing the file: {str(e)}")

    def save_updated_excel(self, df, original_file_path, extension_years):
        # Generate the new file path
        base, ext = os.path.splitext(original_file_path)
        output_file_path = f"{base}_updated_{extension_years}_years{ext}"

        # Check if file already exists
        if os.path.exists(output_file_path):
            # Ask user if they want to overwrite the existing file
            if messagebox.askyesno("Overwrite File",
                                   f"The file {output_file_path} already exists. Do you want to overwrite it?"):
                df.to_excel(output_file_path, index=False)  # Overwrite the existing file
                return output_file_path
            else:
                return None  # Return None if they do not want to overwrite
        else:
            df.to_excel(output_file_path, index=False)  # Save file as it doesn't exist
            return output_file_path

    def apply_extension(self, file_path, extension_years):
        try:
            # Load the Excel file
            df = pd.read_excel(file_path)

            # Ensure the necessary columns are present
            required_columns = ['Operating License', 'Expiration License', 'Capacity MWe']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                missing_columns_str = ", ".join(missing_columns)
                messagebox.showerror(
                    "Missing Columns",
                    f"The following required columns are missing in the selected file: {missing_columns_str}. "
                    "Please select a valid file."
                )
                return

            # Convert date columns
            df['Operating License'] = pd.to_datetime(df['Operating License'], format='%m-%Y')
            df['Expiration License'] = pd.to_datetime(df['Expiration License'], format='%m-%Y')

            # Calculate license durations (in years)
            df['License Duration'] = (
                                             df['Expiration License'] - df['Operating License']
                                     ).dt.days / 365

            # Determine which reactors are *eligible* based on the chosen extension logic
            if extension_years == 150:
                # Example: only extend those with license < 150 years AND expiring before 2050
                cutoff_date = pd.Timestamp(year=2050, month=1, day=1)
                mask = (df['License Duration'] < extension_years) & (df['Expiration License'] < cutoff_date)
            else:
                # General case: eligible if license < extension_years
                mask = df['License Duration'] < extension_years

            # From the user input
            percentage_to_extend = self.extension_percentage_var.get()  # e.g. 100 => 100%
            if percentage_to_extend < 0 or percentage_to_extend > 100:
                messagebox.showerror("Invalid Input", "Percentage must be between 0 and 100.")
                return

            # Make a DataFrame of just the eligible reactors
            eligible_reactors = df[mask].copy()
            num_eligible = len(eligible_reactors)

            if num_eligible == 0:
                messagebox.showinfo("No Extensions",
                                    "No reactors are eligible for an extension based on the chosen criteria.")
                return

            # Figure out how many of these we will extend
            count_to_extend = int(num_eligible * (percentage_to_extend / 100.0))
            if count_to_extend == 0:
                messagebox.showinfo("No Reactors Extended",
                                    "The percentage you entered results in zero reactors being extended.")
                return

            # Randomly select that many reactors from the eligible group
            # random_state=42 is optional if you want reproducible behavior
            selected_to_extend = eligible_reactors.sample(n=count_to_extend)

            # Apply the extension to only those selected
            df.loc[selected_to_extend.index, 'Expiration License'] = (
                    df.loc[selected_to_extend.index, 'Operating License'] + pd.DateOffset(years=extension_years)
            )

            # Count how many were actually extended
            extended_reactors_count = count_to_extend

            # Save updated Excel
            updated_path = self.save_updated_excel(df, file_path, extension_years)
            if updated_path:
                # Update labels and path in the GUI
                self.total_reactors_label.config(text=str(len(df)))  # total rows in the DataFrame
                self.extended_reactors_label.config(text=str(extended_reactors_count))
                self.current_reactors_path_var.set(updated_path)

                messagebox.showinfo(
                    "File Updated",
                    f"Extension applied to {extended_reactors_count} out of {num_eligible} eligible reactors.\n"
                    f"File saved as: {updated_path}"
                )

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while processing the file: {str(e)}")

    def browse_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx")])
        if file_path:
            self.current_reactors_path_var.set(file_path)  # Store the selected file path
            messagebox.showinfo("File Selected", f"File selected: {file_path}")

    def setup_reactor_frame(self):
        # 1. Create the frame first
        self.reactor_frame = ttk.Frame(self.root, padding="10")
        self.reactor_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")

        # 2. Configure its columns (4 columns total)
        for col_index in range(4):
            self.reactor_frame.columnconfigure(col_index, weight=0)

        # Row 0: Main label and radio buttons
        self.future_reactors_label = ttk.Label(
            self.reactor_frame, text="Future Reactors", style="Bold.TLabel"
        )
        self.future_reactors_label.grid(column=0, row=0, padx=5, pady=5, sticky="nsew")

        self.predefined_radio = ttk.Radiobutton(
            self.reactor_frame,
            text="Select from Predefined",
            variable=self.reactor_selection_var,
            value="predefined",
            command=self.update_reactor_entry_visibility
        )
        self.predefined_radio.grid(column=1, row=0, padx=5, pady=5, sticky="nsew")

        self.custom_radio = ttk.Radiobutton(
            self.reactor_frame,
            text="Add Custom Reactor",
            variable=self.reactor_selection_var,
            value="custom",
            command=self.update_reactor_entry_visibility
        )
        self.custom_radio.grid(column=2, row=0, padx=5, pady=5, sticky="nsew")

        self.clear_button = ttk.Button(
            self.reactor_frame,
            text="Clear All Simulation Data",
            command=self.clear_all_data,
            style="Bold.TButton"
        )
        self.clear_button.grid(column=3, row=0, padx=5, pady=5, sticky="nsew")

        # Call predefined and custom reactor sections
        self.setup_predefined_reactor_section()
        self.setup_custom_reactor_section()


        # Row 2: Capacity and Package
        ttk.Label(self.reactor_frame, text="Capacity (MW) per unit:").grid(
            column=0, row=2, padx=5, pady=5, sticky="nsew"
        )
        self.capacity_label = ttk.Label(self.reactor_frame, textvariable=self.capacity_var)
        self.capacity_label.grid(column=1, row=2, padx=5, pady=5, sticky="nsew")

        ttk.Label(self.reactor_frame, text="Number of Units (Package):").grid(
            column=2, row=2, padx=5, pady=5, sticky="w"
        )
        self.package_combobox = ttk.Combobox(
            self.reactor_frame,
            width=10,
            textvariable=self.package_var,
            values=[str(i) for i in range(1, 21)],
            state="readonly"
        )
        self.package_combobox.grid(column=3, row=2, padx=5, pady=5, sticky="nsew")
        self.package_combobox.current(0)

        # Row 3: Mean Growth Rate and Coefficient Variation
        # --- For Mean Growth Rate: Create a sub-frame with label + question mark
        mg_frame = ttk.Frame(self.reactor_frame)
        mg_frame.grid(column=0, row=3, padx=5, pady=5, sticky="nsew")
        mg_label = ttk.Label(mg_frame, text="Mean Growth Rate:")
        mg_label.pack(side="left")
        mg_qmark = ttk.Label(mg_frame, text=" ?", foreground="blue", cursor="question_arrow")
        mg_qmark.pack(side="left")
        ToolTip(mg_qmark, "Enter the average growth rate value for future reactor capacity growth.")

        self.mean_growth_rate_var = DoubleVar(value=0.2)
        self.mean_growth_rate_entry = ttk.Entry(
            self.reactor_frame, width=15, textvariable=self.mean_growth_rate_var
        )
        self.mean_growth_rate_entry.grid(column=1, row=3, padx=5, pady=5, sticky="nsew")

        # --- For Coefficient Variation: Create a sub-frame with label + question mark
        cv_frame = ttk.Frame(self.reactor_frame)
        cv_frame.grid(column=2, row=3, padx=5, pady=5, sticky="nsew")
        cv_label = ttk.Label(cv_frame, text="Coef. Variation of Growth Rate:")
        cv_label.pack(side="left")
        cv_qmark = ttk.Label(cv_frame, text=" ?", foreground="blue", cursor="question_arrow")
        cv_qmark.pack(side="left")
        ToolTip(cv_qmark, "Enter the coefficient (e.g., 0.2) that scales the standard deviation of the growth rate.")

        self.cov_growth_rate_var = DoubleVar(value=0.2)
        self.cov_growth_rate_entry = ttk.Entry(
            self.reactor_frame, width=15, textvariable=self.cov_growth_rate_var
        )
        self.cov_growth_rate_entry.grid(column=3, row=3, padx=5, pady=5, sticky="nsew")

        # Row 4: Growth Function and Growth Rate Distribution
        # --- Growth Function (already with a question mark)
        gf_frame = ttk.Frame(self.reactor_frame)
        gf_frame.grid(column=0, row=4, padx=5, pady=5, sticky="nsew")
        gf_label = ttk.Label(gf_frame, text="Growth Function:")
        gf_label.pack(side="left")
        gf_qmark = ttk.Label(gf_frame, text=" ?", foreground="blue", cursor="question_arrow")
        gf_qmark.pack(side="left")
        ToolTip(gf_qmark,
                "Select the function to model reactor capacity growth.\nOptions: Exponential, Logarithmic, or Linear.")

        self.reactor_growth_function_var = StringVar()
        self.reactor_growth_function_choices = ['Exponential', 'Logarithmic', 'Linear']
        self.reactor_growth_function_combobox = ttk.Combobox(
            self.reactor_frame,
            width=15,
            textvariable=self.reactor_growth_function_var,
            values=self.reactor_growth_function_choices,
            state="readonly"
        )
        self.reactor_growth_function_combobox.grid(column=1, row=4, padx=5, pady=5, sticky="nsew")
        self.reactor_growth_function_combobox.current(0)

        # --- Growth Rate Distribution with question mark
        grd_frame = ttk.Frame(self.reactor_frame)
        grd_frame.grid(column=2, row=4, padx=5, pady=5, sticky="nsew")
        grd_label = ttk.Label(grd_frame, text="Growth Rate Distribution:")
        grd_label.pack(side="left")
        grd_qmark = ttk.Label(grd_frame, text=" ?", foreground="blue", cursor="question_arrow")
        grd_qmark.pack(side="left")
        ToolTip(grd_qmark,
                "Select the distribution for simulating growth rate variations.\nCurrently, only 'Normal' is available.")

        self.growth_rate_distribution_var = StringVar()
        self.growth_rate_distribution_choices = ['Normal']
        self.growth_rate_distribution_combobox = ttk.Combobox(
            self.reactor_frame,
            width=15,
            textvariable=self.growth_rate_distribution_var,
            values=self.growth_rate_distribution_choices,
            state="readonly"
        )
        self.growth_rate_distribution_combobox.grid(column=3, row=4, padx=5, pady=5, sticky="nsew")
        self.growth_rate_distribution_combobox.current(0)

        # Set Bold style for the Clear All button
        style = ttk.Style()
        style.configure("Bold.TButton", font=("Helvetica", 10, "bold"))

    def setup_predefined_reactor_section(self):
        # This method sets up the predefined reactor section in the GUI
        ttk.Label(self.reactor_frame, text="Reactor Identifier:").grid(column=0, row=1, padx=5, pady=5, sticky="nsew")
        # --- NEW Reactor Category Dropdown ---
        ttk.Label(self.reactor_frame, text="Reactor Type:").grid(column=2, row=1, padx=5, pady=5, sticky="nsew")

        self.reactor_category_var = StringVar()
        self.reactor_category_combobox = ttk.Combobox(
            self.reactor_frame,
            width=15,
            textvariable=self.reactor_category_var,
            values= [
            "High-Temperature Gas-Cooled Reactor",
            "Sodium-Cooled Fast Reactor",
            "Fluoride-Salt-Cooled High-Temperature Reactor",
            "Gas-Cooled Fast Reactor",
            "Pressurized Water Reactor",
            "Fast Microreactor",
            "Light Water Reactor"
        ],
            state="readonly"
        )
        self.reactor_category_combobox.grid(column=3, row=1, padx=5, pady=5, sticky="nsew")
        self.reactor_category_combobox.current(0)

        self.reactor_type_combobox = ttk.Combobox(self.reactor_frame, width=25, textvariable=self.reactor_type_var,
                                                  state="readonly")
        self.reactor_type_combobox.grid(column=1, row=1, padx=5, pady=5, sticky="nsew")
        self.reactor_type_combobox['values'] = self.reactor_types  # This is the predefined list
        self.reactor_type_combobox.bind("<<ComboboxSelected>>", self.update_capacity)
        self.reactor_type_combobox.bind("<<ComboboxSelected>>", self.on_reactor_type_selected)

        ttk.Label(self.reactor_frame, text="Capacity (MW) per unit:").grid(column=0, row=2, padx=5, pady=5, sticky="nsew")
        self.capacity_label = ttk.Label(self.reactor_frame, textvariable=self.capacity_var)
        self.capacity_label.grid(column=1, row=2, padx=5, pady=5, sticky="w")

        ttk.Label(self.reactor_frame, text="Number of Units (Package):").grid(column=2, row=2, padx=5, pady=5,
                                                                              sticky="nsew")
        self.package_combobox = ttk.Combobox(self.reactor_frame, width=10, textvariable=self.package_var,
                                             values=[str(i) for i in range(1, 21)], state="readonly")
        self.package_combobox.grid(column=3, row=2, padx=5, pady=5, sticky="nsew")
        self.package_combobox.current(0)

    def setup_custom_reactor_section(self):
        self.custom_reactor_type_label = ttk.Label(self.reactor_frame, text="Custom Reactor Identifier:")
        self.custom_reactor_type_label.grid(column=0, row=3, padx=5, pady=5, sticky="nsew")
        self.custom_reactor_type_entry = ttk.Entry(self.reactor_frame, width=25)
        self.custom_reactor_type_entry.grid(column=1, row=3, padx=5, pady=5, sticky="nsew")

        self.custom_capacity_label = ttk.Label(self.reactor_frame, text="Custom Capacity (MW):")
        self.custom_capacity_label.grid(column=0, row=4, padx=5, pady=5, sticky="nsew")
        self.custom_capacity_entry = ttk.Entry(self.reactor_frame, width=10)
        self.custom_capacity_entry.grid(column=1, row=4, padx=5, pady=5, sticky="nsew")

        # Hide custom reactor section initially
        self.custom_reactor_type_label.grid_remove()
        self.custom_reactor_type_entry.grid_remove()
        self.custom_capacity_label.grid_remove()
        self.custom_capacity_entry.grid_remove()

    def update_capacity(self, event=None):
        selected_reactor = self.reactor_type_var.get()
        if selected_reactor and selected_reactor in self.reactor_types:
            index = self.reactor_types.index(selected_reactor)
            capacity = self.capacities_mw[index]
            self.capacity_var.set(f"{capacity} MW")
        else:
            self.capacity_var.set('')  # Clear the capacity display if the reactor is not in the list

    def on_reactor_type_selected(self, event=None):
        self.update_capacity()
        self.update_category_on_type_selection()


    def update_category_on_type_selection(self, event=None):
        selected_type = self.reactor_type_var.get()
        category = self.reactor_type_to_category.get(selected_type, "")
        self.reactor_category_var.set(category)


    def update_reactor_entry_visibility(self):
        selection = self.reactor_selection_var.get()
        if selection == "predefined":
            # Show predefined reactor section
            self.reactor_type_combobox.grid(column=1, row=1, padx=5, pady=5, sticky="nsew")
            self.capacity_label.grid(column=1, row=2, padx=5, pady=5, sticky="nsew")

            self.reactor_category_combobox.grid(column=3, row=1, padx=5, pady=5, sticky="nsew")
            self.reactor_category_entry.grid_remove()

            # Hide custom reactor section
            self.custom_reactor_type_label.grid_remove()
            self.custom_reactor_type_entry.grid_remove()
            self.custom_capacity_label.grid_remove()
            self.custom_capacity_entry.grid_remove()

            self.custom_reactor_type_entry.delete(0, END)
            self.custom_capacity_entry.delete(0, END)

        elif selection == "custom":
            # Show custom reactor section
            self.reactor_category_var.set("")  # clears Option 1 when custom selected
            self.custom_reactor_type_label.grid(column=0, row=1, padx=5, pady=5, sticky="nsew")
            self.custom_reactor_type_entry.grid(column=1, row=1, padx=5, pady=5, sticky="nsew")
            self.custom_capacity_label.grid(column=0, row=2, padx=5, pady=5, sticky="nsew")
            self.custom_capacity_entry.grid(column=1, row=2, padx=5, pady=5, sticky="nsew")

            # Hide predefined dropdowns
            self.reactor_type_combobox.grid_remove()
            self.capacity_label.grid_remove()

            # 🔁 Hide category dropdown and show text entry
            self.reactor_category_combobox.grid(column=3, row=1, padx=5, pady=5, sticky="nsew")

            # Clear values
            self.capacity_var.set('')

    def edit_reactor(self):
        selected_items = self.reactor_table.selection()

        if not selected_items:
            messagebox.showerror("Error", "Please select one or more reactors to delete.")
            return

        # Prompt user for confirmation
        if messagebox.askyesno("Delete Reactor", "Are you sure you want to delete the selected reactors?"):
            # Delete the selected reactors from both the Treeview and the internal lists
            for selected_item in selected_items:
                item_index = self.reactor_table.index(selected_item)

                # Remove the reactor info from the internal lists (user-added reactors only)
                self.reactors.pop(item_index)
                self.growth_functions.pop(item_index)

                # Remove the reactor from the Treeview
                self.reactor_table.delete(selected_item)

            messagebox.showinfo("Success", "Selected reactors have been deleted.")

    def setup_list_frame(self):
        self.list_frame = ttk.Frame(self.root, padding="10")
        self.list_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

        # Define the bold style for the label
        style = ttk.Style()
        style.configure("Bold.TLabel", font=("Helvetica", 10, "bold"))

        # Add a label for "Display Results"
        display_label = tk.Label(self.list_frame, text="Added Future Reactors:", font=("Arial", 10, "bold"))
        display_label.grid(row=0, column=0, sticky="nsew", pady=(0, 5))  # Add bottom padding to separate from text box

        # Add the Edit button to the right of the Display Results label
        self.edit_button = ttk.Button(self.list_frame, text="Delete Reactor", command=self.edit_reactor, width=14)
        self.edit_button.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")

        # Add the Add Reactor button next to the Delete button
        self.add_reactor_button = ttk.Button(self.list_frame, text="Add Reactor", command=self.add_reactor, width=14)
        self.add_reactor_button.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")

        # Create a Treeview widget to display reactors as a table
        columns = ("Reactor Identifier", "Reactor Type", "Capacity (MW)", "Growth Rate", "Package", "Growth Function")
        self.reactor_table = ttk.Treeview(self.list_frame, columns=columns, show='headings', height=10,
                                          selectmode='extended')

        # Define column headings
        self.reactor_table.heading("Reactor Identifier", text="Reactor Identifier")
        self.reactor_table.heading("Reactor Type", text="Reactor Type")
        self.reactor_table.column("Reactor Type", width=150, anchor="center")
        self.reactor_table.heading("Capacity (MW)", text="Capacity (MW)")
        self.reactor_table.heading("Growth Rate", text="Growth Rate")
        self.reactor_table.heading("Package", text="Package")
        self.reactor_table.heading("Growth Function", text="Growth Function")

        # Define column widths
        self.reactor_table.column("Reactor Identifier", width=150, anchor="center")
        self.reactor_table.column("Capacity (MW)", width=100, anchor="center")
        self.reactor_table.column("Growth Rate", width=100, anchor="center")
        self.reactor_table.column("Package", width=80, anchor="center")
        self.reactor_table.column("Growth Function", width=120, anchor="center")

        self.reactor_table.grid(row=1, column=0, columnspan=3, sticky="nsew")

        # Add vertical scrollbar for Treeview
        scrollbar = ttk.Scrollbar(self.list_frame, orient="vertical", command=self.reactor_table.yview)
        self.reactor_table.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=1, column=3, sticky='nsew')

        # Configure grid resizing for the list frame
        self.list_frame.columnconfigure(0, weight=1)
        self.list_frame.columnconfigure(1, weight=1)
        self.list_frame.columnconfigure(2, weight=1)
        self.list_frame.columnconfigure(3, weight=1)  # scrollbar column

    def setup_goals_frame(self):
        self.goals_frame = ttk.Frame(self.root, padding="10")
        self.goals_frame.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")

        # Define a custom style for the button
        style = ttk.Style()
        style.configure("Custom.TButton",
                        font=("Helvetica", 10, "bold"),
                        background="#3498db",
                        foreground="black",
                        padding=10,
                        relief="raised",
                        borderwidth=2)
        style.map("Custom.TButton",
                  background=[('active', '#2980b9')],  # Color when the button is pressed
                  foreground=[('disabled', 'gray')])

        # Create the button with the custom style
        self.new_button = ttk.Button(self.goals_frame, text="Future Mean Distribution Info",
                                     command=lambda: messagebox.showinfo("Future Mean Distribution",
                                                                         "NEI is predicting that there would be 90,000 MW added by the end of 2050."),
                                     width=25, style="Custom.TButton")
        self.new_button.grid(column=0, row=0, columnspan=2, padx=5, pady=5, sticky="nsew")

        ttk.Label(self.goals_frame, text="Total Mean Future Capacity (MW):").grid(column=0, row=1, padx=5, pady=5,
                                                                                  sticky="nsew")
        self.total_capacity_goal_var = IntVar(value=90000)

        self.total_capacity_goal_entry = ttk.Entry(self.goals_frame, width=15,
                                                   textvariable=self.total_capacity_goal_var)
        self.total_capacity_goal_entry.grid(column=1, row=1, padx=2, pady=2, sticky="nsew")

        self.plot_future_capacity_button = ttk.Button(self.goals_frame, text="Plot Future Capacity Distribution",
                                                      command=self.plot_future_capacity_distribution, width=35,
                                                      style="Custom.TButton")
        self.plot_future_capacity_button.grid(column=2, row=0, padx=5, pady=5, sticky="ew")
        ttk.Label(self.goals_frame, text="Coef. Variation of Future Capacity:").grid(column=2, row=1, padx=5, pady=5, sticky="nsew")
        self.coefficient_variation_var = DoubleVar(value=0.2)
        self.coefficient_variation_entry = ttk.Entry(self.goals_frame, width=10,
                                                     textvariable=self.coefficient_variation_var)
        self.coefficient_variation_entry.grid(column=3, row=1, padx=2, pady=2, sticky="nsew")

        ttk.Label(self.goals_frame, text="Future Capacity Distribution:").grid(column=0, row=2, padx=5, pady=5,
                                                                               sticky="nsew")
        self.capacity_distribution_var = StringVar()
        self.capacity_distribution_choices = ['Normal']
        self.capacity_distribution_combobox = ttk.Combobox(self.goals_frame, width=15,
                                                           textvariable=self.capacity_distribution_var,
                                                           values=self.capacity_distribution_choices, state="readonly")
        self.capacity_distribution_combobox.grid(column=1, row=2, padx=5, pady=5, sticky="nsew")
        self.capacity_distribution_combobox.current(0)

        ttk.Label(self.goals_frame, text="Number of Simulations:").grid(column=2, row=2, padx=5, pady=5, sticky="nsew")
        self.num_simulations_var = IntVar(value=1000)
        self.num_simulations_entry = ttk.Entry(self.goals_frame, width=10, textvariable=self.num_simulations_var)
        self.num_simulations_entry.grid(column=3, row=2, padx=5, pady=5, sticky="nsew")

        ttk.Label(self.goals_frame, text="Deployment Years:").grid(column=0, row=3, padx=5, pady=5, sticky="nsew")
        self.specific_years_var = StringVar()
        self.specific_years_combobox = ttk.Combobox(self.goals_frame, width=35, textvariable=self.specific_years_var,
                                                    state="readonly")
        self.specific_years_combobox['values'] = ['2025, 2030, 2035, 2040, 2045, 2050']
        self.specific_years_combobox.grid(column=1, row=3, columnspan=3, padx=5, pady=5, sticky="nsew")
        self.specific_years_combobox.current(0)

        self.add_goals_button = ttk.Button(self.goals_frame, text="Export and Simulate Future Reactors",
                                           command=self.set_goals, width=25)
        self.add_goals_button.grid(column=0, row=4, columnspan=2, padx=5, pady=5, sticky="nsew")

        self.capacity_breakdown_button = ttk.Button(self.goals_frame, text="Capacity Breakdown Future Reactors",
                                                    command=self.capacity_breakdown, width=40)
        self.capacity_breakdown_button.grid(column=2, row=4, columnspan=2, padx=5, pady=5, sticky="nsew")

        # New button to plot capacity added from future reactors
        self.plot_future_reactor_capacity_button = ttk.Button(self.goals_frame,
                                                              text="Plot Future Capacity Reactors",
                                                              command=self.plot_future_reactor_capacity, width=40)
        self.plot_future_reactor_capacity_button.grid(column=2, row=5, columnspan=2, padx=5, pady=5, sticky="nsew")

    def plot_future_capacity_distribution(self):
        # Get the mean and coefficient of variation
        mean_capacity = self.total_capacity_goal_var.get()
        coefficient_of_variation = self.coefficient_variation_var.get()
        distribution_type = self.capacity_distribution_var.get()

        if distribution_type == 'Normal':
            # Generate Normal distribution data
            stddev = mean_capacity * coefficient_of_variation
            simulations = np.random.normal(loc=mean_capacity, scale=stddev, size=self.num_simulations_var.get())

            # Plot the distribution using matplotlib
            plt.figure(figsize=(10, 5))
            sns.histplot(simulations, bins=30, kde=True, color='skyblue')
            plt.title(
                f'Normal Distribution of Future Capacities (Mean: {mean_capacity}, CoV: {coefficient_of_variation})')
            plt.xlabel('Capacity (MW)')
            plt.ylabel('Frequency')
            plt.grid(True)
            plt.show()
        else:
            messagebox.showinfo("Not Implemented", "Only Normal distribution is implemented for now.")

    def plot_future_reactor_capacity(self):
        if not self.future_capacities_cum:
            messagebox.showerror("Error", "Please simulate future capacities before plotting.")
            return

        # Extract future capacities (excluding current capacities)
        future_capacities_only = self.future_capacities_cum

        # Prepare data for plotting
        years = [2025, 2030, 2035, 2040, 2045, 2050]
        data_by_year = {year: [] for year in years}

        for scenario in future_capacities_only:
            for year, capacity in zip(years, future_capacities_only[scenario]):
                data_by_year[year].append(capacity)

        # Convert data to a format suitable for seaborn
        data_for_violinplot = []
        for year in years:
            for value in data_by_year[year]:
                data_for_violinplot.append((year, value))

        df = pd.DataFrame(data_for_violinplot, columns=['Year', 'Capacity'])

        # Define a custom color palette
        custom_palette = ["#3498db", "#2ecc71", "#e74c3c", "#9b59b6", "#f1c40f", "#1abc9c"]

        # Create the violin plot with smaller figure size
        plt.figure(figsize=(10, 6))  # Decrease figure size
        sns.violinplot(x='Year', y='Capacity', data=df, hue='Year', palette=custom_palette, legend=False)

        # Larger font sizes for labels and ticks
        plt.title('Capacity Added from Future Reactors Over Time', fontsize=20)
        plt.xlabel('Year', fontsize=18)
        plt.ylabel('Capacity (MW)', fontsize=18)
        plt.grid(True)

        # Increase the font size of the tick labels
        plt.tick_params(axis='both', which='major', labelsize=16)

        plt.show()

    def add_reactor(self):
        # Determine the reactor type (either selected from dropdown or entered manually)
        reactor_type = self.reactor_type_var.get() if self.reactor_type_var.get() else self.custom_reactor_type_entry.get()

        # Get the capacity value from either dropdown or entry
        capacity = self.capacity_var.get() if self.capacity_var.get() else self.custom_capacity_entry.get()

        # Get the reactor category (from dropdown, always present for both predefined and custom)
        category = self.reactor_category_var.get()

        # Clean up capacity input (remove ' MW' if present)
        if capacity and capacity.endswith(' MW'):
            capacity = capacity[:-3]

        # Validate reactor type and capacity inputs
        if not reactor_type or not capacity:
            messagebox.showerror("Invalid Input",
                                 "Please select a reactor type or enter a custom one, and specify its capacity.")
            return

        try:
            capacity = float(capacity)
            package = int(self.package_var.get())
            if package <= 0:
                raise ValueError("Number of units must be greater than zero.")
        except ValueError:
            messagebox.showerror("Invalid Input",
                                 "Please enter a valid capacity and number of units (positive integer).")
            return

        # Get the user-provided Mean Growth Rate and CoV
        mean_growth_rate = self.mean_growth_rate_var.get()
        cov_growth_rate = self.cov_growth_rate_var.get()

        # 👉 Store custom reactor type → category mapping
        if reactor_type not in self.reactor_type_to_category:
            self.reactor_type_to_category[reactor_type] = category

        # Store the reactor info
        reactor_info = (reactor_type, capacity, mean_growth_rate, package)
        self.reactors.append(reactor_info)

        # Store growth function (selected per reactor)
        growth_function_input = self.reactor_growth_function_var.get()
        self.growth_functions.append(growth_function_input)

        # Insert reactor into Treeview table
        self.reactor_table.insert("", "end", values=(
            reactor_type,
            category,
            f"{capacity} MW",
            f"Mean: {mean_growth_rate}, CoV: {cov_growth_rate}",
            package,
            growth_function_input
        ))

        # Clear input fields after adding
        self.reactor_type_combobox.set('')
        self.custom_reactor_type_entry.delete(0, END)
        self.capacity_var.set('')
        self.custom_capacity_entry.delete(0, END)
        self.package_combobox.set('1')
        self.reactor_growth_function_combobox.current(0)

    def gather_simulation_data(self):
        reactor_types = []
        capacities_mw = []
        num_units_list = []

        reactor_parameters = {}

        for reactor_info in self.reactors:
            reactor_type, unit_capacity, mean_growth_rate, num_units = reactor_info
            reactor_types.append(reactor_type)
            capacities_mw.append(unit_capacity * num_units)
            num_units_list.append(num_units)

            # Get user-provided values for mean and CoV
            cov_growth_rate = self.cov_growth_rate_var.get()

            # Calculate the standard deviation using mean and CoV
            std_growth_rate = mean_growth_rate * cov_growth_rate

            # Store the mean and calculated std for each reactor
            reactor_parameters[reactor_type] = {
                "mean": mean_growth_rate,
                "std": std_growth_rate  # Standard deviation is calculated based on the CoV
            }

        total_capacity_goal = int(self.total_capacity_goal_var.get())

        simulation_data = {
            "reactor_types": reactor_types,
            "capacities_mw": capacities_mw,
            "num_units": num_units_list,
            "total_capacity_goal": total_capacity_goal,
            "specific_years": [int(year.strip()) for year in self.specific_years_var.get().split(',')],
            "num_simulations": self.num_simulations_var.get(),
            "reactor_parameters": reactor_parameters,
            "growth_functions": self.growth_functions,  # Add the growth functions
        }

        return simulation_data

    def set_goals(self):
        if not self.reactors:
            messagebox.showerror("Error", "Please add at least one reactor before simulating.")
            return

        # Gather necessary simulation data
        simulation_data = self.gather_simulation_data()
        num_simulations = simulation_data["num_simulations"]
        reactor_types = simulation_data["reactor_types"]
        specific_years = simulation_data["specific_years"]
        capacities_mw = simulation_data["capacities_mw"]
        total_capacity_goal = simulation_data["total_capacity_goal"]

        # Access user-provided mean growth rate and CoV
        mean_growth_rate = self.mean_growth_rate_var.get()
        cov_growth_rate = self.cov_growth_rate_var.get()

        # Calculate the difference in years from the base year (2025)
        years_difference = np.array(specific_years) - 2025
        years_difference = years_difference.reshape(-1, 1)

        # Get the growth functions for each reactor
        growth_functions = simulation_data["growth_functions"]

        try:
            # Simulate the growth rates for the reactors using the user-provided values
            scaled_values, deployed_reactors, deployments_per_type = vectorized_full_simulate_reactor_growth(
                reactor_types, simulation_data["reactor_parameters"], specific_years, num_simulations,
                growth_functions, capacities_mw,
                generate_normal_sample(total_capacity_goal, cov_growth_rate, num_simulations),  # Future capacities
                years_difference,
                mean_growth_rate, cov_growth_rate  # Pass user-provided values
            )
            # Step 1: Make scaled_values cumulative over years
            cumulative_scaled_array = np.cumsum(scaled_values, axis=1)

            # Step 2: Create nested dictionary: scenario -> year -> reactor type -> capacity
            self.future_capacity_by_type_cumulative = {}
            for sim_idx in range(cumulative_scaled_array.shape[0]):
                scenario_name = f"Scenario {sim_idx + 1}"
                self.future_capacity_by_type_cumulative[scenario_name] = {}

                for year_idx, year in enumerate(simulation_data["specific_years"]):
                    self.future_capacity_by_type_cumulative[scenario_name][year] = {}

                    for reactor_idx, reactor_type in enumerate(simulation_data["reactor_types"]):
                        capacity = float(cumulative_scaled_array[sim_idx, year_idx, reactor_idx])
                        # Get category for the current reactor type
                        category = self.reactor_type_to_category.get(reactor_type, "Custom or Unknown")

                        # Initialize category dict if not already present
                        if category not in self.future_capacity_by_type_cumulative[scenario_name][year]:
                            self.future_capacity_by_type_cumulative[scenario_name][year][category] = {}

                        # Store capacity under category -> reactor_type
                        self.future_capacity_by_type_cumulative[scenario_name][year][category][reactor_type] = capacity

            # Calculate the cumulative total capacity over time
            self.future_capacities_cum = calculate_cumulative_total_capacity(scaled_values)
            self.deployments_per_type = deployments_per_type  # Store deployments for each reactor type

            # Notify the user that the simulation is complete
            messagebox.showinfo("Simulation Complete", "Future capacities have been simulated successfully.")

            # Call export_to_excel to save the deployed reactors data
            self.export_to_excel(deployed_reactors)

        except Exception as e:
            # Handle any errors that occur during the simulation
            messagebox.showerror("Simulation Error", str(e))


    def plot_total_projection(self):
        # Check if current capacities are loaded and simulations are run
        if not self.current_total_capacities:
            messagebox.showerror("Error", "Please load current reactor capacities before plotting.")
            return

        # Check if future capacities have been simulated
        if not self.future_capacities_cum:
            messagebox.showerror("Error", "Please simulate future capacities before plotting.")
            return

        try:
            combined_capacities = self.combine_current_and_future_capacities(self.current_total_capacities,
                                                                             self.future_capacities_cum)
            # Call the display_combined_capacities method with smaller figure size and larger tick font sizes
            self.display_combined_capacities(combined_capacities, axis_font_size=18, tick_font_size=16)
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def display_combined_capacities(self, combined_capacities, axis_font_size=18, tick_font_size=16):
        plt.figure(figsize=(10, 6))  # Decrease figure size

        # Prepare data for plotting
        years = [2025, 2030, 2035, 2040, 2045, 2050]
        data_by_year = {year: [] for year in years}

        for scenario in combined_capacities:
            for year, capacity in zip(years, combined_capacities[scenario]):
                data_by_year[year].append(capacity)

        # Convert data to a format suitable for seaborn
        data_for_violinplot = []
        for year in years:
            for value in data_by_year[year]:
                data_for_violinplot.append((year, value))

        df = pd.DataFrame(data_for_violinplot, columns=['Year', 'Capacity'])

        # Define a custom color palette
        custom_palette = ["#3498db", "#2ecc71", "#e74c3c", "#9b59b6", "#f1c40f", "#1abc9c"]

        # Create the violin plot
        sns.boxplot(x='Year', y='Capacity', data=df, hue='Year', palette=custom_palette, legend=False)

        plt.title('Total Projected Reactor Capacities Over Time', fontsize=axis_font_size + 2)
        plt.xlabel('Year', fontsize=axis_font_size)
        plt.ylabel('Total Capacity (MW)', fontsize=axis_font_size)
        plt.grid(True)

        # Increase the font size of the tick labels
        plt.tick_params(axis='both', which='major', labelsize=tick_font_size)

        plt.show()
    def export_to_excel(self, deployed_reactors):
        """
        Export the simulation results, specifically the number of reactors deployed, to an Excel file.

        Parameters:
        deployed_reactors (numpy.ndarray): A 3D array representing the deployed reactors for each simulation, year, and reactor type.
        """
        try:
            # Reshape the deployed_reactors array into a 2D format
            num_simulations, num_years, num_reactors = deployed_reactors.shape
            deployed_reactors_2d = deployed_reactors.reshape(num_simulations * num_years, num_reactors)

            # Get the list of reactor types actually being simulated
            simulated_reactor_types = [reactor_info[0] for reactor_info in self.reactors]  # Only use simulated reactors

            # Check the shape of the reshaped data
            print(f"Reshaped deployed_reactors_2d shape: {deployed_reactors_2d.shape}")  # Debugging line

            # Create a list of simulation indices and specific years to go with the data
            simulation_indices = np.repeat(np.arange(num_simulations), num_years)
            specific_years = np.tile(np.array(self.specific_years_var.get().split(','), dtype=int), num_simulations)

            # Ensure the number of reactor types matches the number of columns
            if len(simulated_reactor_types) != num_reactors:
                raise ValueError(
                    f"Number of reactor types ({len(simulated_reactor_types)}) does not match the number of reactors ({num_reactors}) in the data.")

            # Create a DataFrame from the reshaped data and additional columns for simulation index and year
            df = pd.DataFrame(deployed_reactors_2d, columns=simulated_reactor_types)

            # Add the 'Simulation Index' and 'Specific Year' columns
            df.insert(0, 'Simulation Index', simulation_indices)
            df.insert(1, 'Specific Year', specific_years)

            # Check if the number of columns matches
            print(f"DataFrame shape: {df.shape}")  # Debugging line

            # Prompt user to choose a file name for the Excel file
            file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])

            if file_path:
                # Export the DataFrame to Excel
                df.to_excel(file_path, index=False)
                messagebox.showinfo("Export Successful", f"Data has been successfully exported to {file_path}")
            else:
                messagebox.showerror("Export Error", "No file selected. Export canceled.")

        except Exception as e:
            messagebox.showerror("Export Error", f"An error occurred while exporting to Excel: {str(e)}")


def show_main_app():
    gui = ReactorGUI(root)
    # Set the window size to the maximum display size
    try:
        root.state('zoomed')  # For Windows
    except:
        root.attributes('-fullscreen', True)  # For other platforms # Ensure the main application window is the same size

if __name__ == "__main__":
    import ctypes

    try:
        # Works for Windows 8.1 and later
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # SYSTEM_DPI_AWARE
    except Exception:
        try:
            # Works for older versions of Windows (Windows 7 and earlier)
            ctypes.windll.user32.SetProcessDPIAware()
        except:
            pass

    root = ThemedTk(theme="breeze")
    root.title("RENEWS: Reactor Expansion & Nuclear Employment Workforce Simulator")
    root.minsize(1200, 750)  # <- Add this line
    WelcomePage(root, show_main_app)  # Show the welcome page first
    root.mainloop()

