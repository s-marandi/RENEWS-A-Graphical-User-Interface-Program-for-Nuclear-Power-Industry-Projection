import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import math
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt

class FuelCycleWindow(tk.Toplevel):
    def __init__(self, parent, selected_demand_level_var, current_capacities,
                 future_capacities,num_simulations):
        super().__init__(parent)
        self.title("Fuel Cycle Demand")
        self.geometry("800x1000")
        self.current_total_capacities = current_capacities
        self.future_capacities_cum = future_capacities
        self.num_simulations = num_simulations

        # Scenario variables
        self.selected_current_scenario = tk.StringVar()
        self.selected_future_scenario = tk.StringVar()
        self.selected_current_scenario.set("Moderate")
        self.selected_future_scenario.set("Moderate")

        # Default demand factors per GWea for each stage (Current & Future)
        self.fuel_cycle_demand_factors = {
            "Uranium Ore (Mining)": {
                "Moderate": {"current": 104677.72, "new": 143670.17}
            },
            "U3O8 (Milling)": {
                "Moderate": {"current": 236.41, "new": 324.48}
            },
            "UF6 (Natural) (Conversion)": {
                "Moderate": {"current": 295.00, "new": 404.89}
            },
            "UF6 (Enriched) (Enrichment)": {
                "Moderate": {"current": 35.45, "new": 13.64}
            },
            "UO2 (Fuel Fabrication)": {
                "Moderate": {"current": 26.92, "new": 10.36}
            }
        }

        # For uranium ore, you may already be using a separate uranium_demand_function.
        # Store it along with the currently selected scenario and capacity data.
        self.selected_demand_level_var = selected_demand_level_var
        if not self.selected_demand_level_var.get():
            self.selected_demand_level_var.set("Scenario 3")

        self.current_total_capacities = current_capacities
        self.future_capacities_cum = future_capacities

        # --- Fuel cycle description
        description = (
            "The nuclear fuel cycle includes the following stages:\n"
            "- Mining\n"
            "- Milling\n"
            "- Conversion\n"
            "- Enrichment\n"
            "- Fuel Fabrication\n"
        )
        ttk.Label(self, text="Fuel Cycle Overview", font=("Arial", 12, "bold")).pack(pady=5)
        ttk.Label(self, text=description, wraplength=400, justify="left").pack(padx=10, pady=5)

        # --- Control Buttons (replaced assumption buttons with direct demand input)
        control_frame = ttk.Frame(self)
        control_frame.pack(pady=10)

        ttk.Button(
            control_frame,
            text="Enter Demand Factors (Current & Future)",
            command=self.enter_demand_inputs
        ).pack(side="left", padx=5)

        # --- Stage-specific plotting buttons
        step_buttons_frame = ttk.LabelFrame(self, text="Plot Demand by Stage")
        step_buttons_frame.pack(padx=10, pady=5, fill="x")

        ttk.Button(step_buttons_frame, text="Plot Uranium Ore Demand (Mining)", command=self.plot_uranium_ore).pack(
            pady=2, fill="x")
        ttk.Button(step_buttons_frame, text="Plot U3O8 Demand (Milling)", command=self.plot_u3o8).pack(pady=2, fill="x")
        ttk.Button(step_buttons_frame, text="Plot UF6 (Natural) Demand (Conversion)", command=self.plot_uf6_nat).pack(
            pady=2, fill="x")
        ttk.Button(step_buttons_frame, text="Plot UF6 (Enriched) Demand (Enrichment)",
                   command=self.plot_uf6_enriched).pack(pady=2, fill="x")
        ttk.Button(step_buttons_frame, text="Plot UO2 Demand (Fuel Fabrication)", command=self.plot_uo2).pack(pady=2,
                                                                                                              fill="x")
        # Checkbox to include fuel cycle workforce
        self.include_fuel_cycle_workforce = tk.BooleanVar(value=False)

        ttk.Checkbutton(
            self,
            text="Include fuel cycle workforce in workforce projection",
            variable=self.include_fuel_cycle_workforce,
            onvalue=True,
            offvalue=False
        ).pack(pady=5)

        ttk.Label(self, text="Fuel Cycle Workforce Factors (Number of people) per Unit Demand", font=("Arial", 11, "bold")).pack(
            pady=5)

        self.workforce_config = {}  # Holds full config per stage

        factor_frame = ttk.Frame(self)
        factor_frame.pack(padx=10, pady=5, fill="x")

        stages = [
            "Uranium Ore (Mining)",
            "U3O8 (Milling)",
            "UF6 (Natural) (Conversion)",
            "UF6 (Enriched) (Enrichment)",
            "UO2 (Fuel Fabrication)"
        ]
        self.stages = stages
        ttk.Button(
            self,
            text="Plot Total Fuel Cycle Workforce",
            command=self.simulate_and_plot_total_workforce
        ).pack(pady=8)

        def update_fields(stage):
            """Show/hide fields based on selected distribution"""
            dist = self.workforce_config[stage]['distribution'].get()
            if dist == "Uniform":
                self.workforce_config[stage]['low_label'].pack(side="left")
                self.workforce_config[stage]['low_entry'].pack(side="left", padx=2)
                self.workforce_config[stage]['high_label'].pack(side="left")
                self.workforce_config[stage]['high_entry'].pack(side="left", padx=2)
                self.workforce_config[stage]['mean_label'].pack_forget()
                self.workforce_config[stage]['mean_entry'].pack_forget()
                self.workforce_config[stage]['cov_label'].pack_forget()
                self.workforce_config[stage]['cov_entry'].pack_forget()
            else:  # Normal
                self.workforce_config[stage]['low_label'].pack_forget()
                self.workforce_config[stage]['low_entry'].pack_forget()
                self.workforce_config[stage]['high_label'].pack_forget()
                self.workforce_config[stage]['high_entry'].pack_forget()
                self.workforce_config[stage]['mean_label'].pack(side="left")
                self.workforce_config[stage]['mean_entry'].pack(side="left", padx=2)
                self.workforce_config[stage]['cov_label'].pack(side="left")
                self.workforce_config[stage]['cov_entry'].pack(side="left", padx=2)

        stage_label_display = {
            "Uranium Ore (Mining)": "People Per 1000 tons of Uranium Ore (Mining)",
            "U3O8 (Milling)" : "People Per 1000 tons of U3O8 (Milling) ",
            "UF6 (Natural) (Conversion)": "People Per 1000 tons UF6 (Natural) (Conversion)",
            "UF6 (Enriched) (Enrichment)" : "People Per 1000 tons UF6 (Enriched) (Enrichment)",
            "UO2 (Fuel Fabrication)" : "People Per 1000 tons UO2 (Fuel Fabrication)"
        }

        for stage in stages:
            row = ttk.Frame(factor_frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=stage_label_display.get(stage, stage) + ":", width=43, anchor="w").pack(side="left")
            dist_var = tk.StringVar(value="Uniform")
            dist_menu = ttk.Combobox(row, textvariable=dist_var, values=["Uniform", "Normal"], state="readonly",
                                     width=10)
            dist_menu.pack(side="left", padx=5)

            input_frame = ttk.Frame(row)
            input_frame.pack(side="left", padx=5)

            # Uniform fields
            low_var = tk.DoubleVar()
            high_var = tk.DoubleVar()
            low_label = ttk.Label(input_frame, text="Low:")
            low_entry = ttk.Entry(input_frame, textvariable=low_var, width=7)
            high_label = ttk.Label(input_frame, text="High:")
            high_entry = ttk.Entry(input_frame, textvariable=high_var, width=7)

            # Normal fields
            mean_var = tk.DoubleVar()
            cov_var = tk.DoubleVar()
            mean_label = ttk.Label(input_frame, text="Mean:")
            mean_entry = ttk.Entry(input_frame, textvariable=mean_var, width=7)
            cov_label = ttk.Label(input_frame, text="CoV:")
            cov_entry = ttk.Entry(input_frame, textvariable=cov_var, width=7)

            # Button on the far right
            ttk.Button(row, text="Plot Testing",
                       command=lambda s=stage: self.simulate_and_plot_workforce(s)).pack(side="right")

            self.workforce_config[stage] = {
                "distribution": dist_var,
                "low": low_var,
                "high": high_var,
                "mean": mean_var,
                "cov": cov_var,
                "low_label": low_label,
                "low_entry": low_entry,
                "high_label": high_label,
                "high_entry": high_entry,
                "mean_label": mean_label,
                "mean_entry": mean_entry,
                "cov_label": cov_label,
                "cov_entry": cov_entry
            }

            if stage == "Uranium Ore (Mining)":
                low_var.set(3.1e-4*1000)
                high_var.set(4.7e-4*1000)
                mean_var.set(0.0004*1000)
                cov_var.set(0.11)

            elif stage == "U3O8 (Milling)":
                low_var.set(0.034*1000)
                high_var.set(0.127*1000)
                mean_var.set(0.1015*1000)
                cov_var.set(0.13)

            elif stage == "UF6 (Natural) (Conversion)":
                low_var.set(0.027*1000)
                high_var.set(0.030*1000)
                mean_var.set(0.028*1000)
                cov_var.set(0.029)

            elif stage == "UF6 (Enriched) (Enrichment)":
                low_var.set(0.56*1000)
                high_var.set(0.73*1000)
                mean_var.set(0.645*1000)
                cov_var.set(0.066)

            elif stage == "UO2 (Fuel Fabrication)":
                low_var.set(0.6*1000)
                high_var.set(1.0*1000)
                mean_var.set(0.70*1000)
                cov_var.set(0.071)

            def update_fields(stage_name=stage):
                dist = self.workforce_config[stage_name]['distribution'].get()
                if dist == "Uniform":
                    self.workforce_config[stage_name]['low_label'].pack(side="left")
                    self.workforce_config[stage_name]['low_entry'].pack(side="left", padx=2)
                    self.workforce_config[stage_name]['high_label'].pack(side="left")
                    self.workforce_config[stage_name]['high_entry'].pack(side="left", padx=2)
                    self.workforce_config[stage_name]['mean_label'].pack_forget()
                    self.workforce_config[stage_name]['mean_entry'].pack_forget()
                    self.workforce_config[stage_name]['cov_label'].pack_forget()
                    self.workforce_config[stage_name]['cov_entry'].pack_forget()
                else:
                    self.workforce_config[stage_name]['low_label'].pack_forget()
                    self.workforce_config[stage_name]['low_entry'].pack_forget()
                    self.workforce_config[stage_name]['high_label'].pack_forget()
                    self.workforce_config[stage_name]['high_entry'].pack_forget()
                    self.workforce_config[stage_name]['mean_label'].pack(side="left")
                    self.workforce_config[stage_name]['mean_entry'].pack(side="left", padx=2)
                    self.workforce_config[stage_name]['cov_label'].pack(side="left")
                    self.workforce_config[stage_name]['cov_entry'].pack(side="left", padx=2)

            update_fields(stage)
            dist_menu.bind("<<ComboboxSelected>>", lambda e, s=stage: update_fields(s))

        self.transient(parent)
        self.grab_set()
        self.focus_set()
        self.wait_window(self)

    #Direct Demand Input UI
    def enter_demand_inputs(self):
        popup = tk.Toplevel(self)
        popup.title("Enter Demand per GWa\u2091")
        popup.geometry("740x520")

        defaults = getattr(self, "default_demand_factors", {
            "Uranium Ore (Mining)": {"Moderate": {"current": 104677.72, "new": 143670.17}},
            "U3O8 (Milling)": {"Moderate": {"current": 236.41, "new": 324.48}},
            "UF6 (Natural) (Conversion)": {"Moderate": {"current": 295.00, "new": 404.89}},
            "UF6 (Enriched) (Enrichment)": {"Moderate": {"current": 35.45, "new": 13.64}},
            "UO2 (Fuel Fabrication)": {"Moderate": {"current": 26.92, "new": 10.36}},
        })

        if not hasattr(self, "fuel_cycle_demand_factors") or not self.fuel_cycle_demand_factors:
            self.fuel_cycle_demand_factors = {
                k: {"Moderate": {"current": v["Moderate"]["current"], "new": v["Moderate"]["new"]}}
                for k, v in defaults.items()
            }

        if not hasattr(self, "stages") or not self.stages:
            self.stages = list(defaults.keys())

        self.demand_vars_current = {}
        self.demand_vars_future = {}

        frame = ttk.Frame(popup)
        frame.pack(padx=10, pady=5, fill="x")

        ttk.Label(frame, text="Stage", width=34).grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text="Current (tonnes)").grid(row=0, column=1)
        ttk.Label(frame, text="Future (tonnes)").grid(row=0, column=2)

        # Prefill from last saved values; fallback to defaults
        for i, stage in enumerate(self.stages):
            saved_cur = (self.fuel_cycle_demand_factors.get(stage, {})
                         .get("Moderate", {})
                         .get("current", defaults[stage]["Moderate"]["current"]))
            saved_new = (self.fuel_cycle_demand_factors.get(stage, {})
                         .get("Moderate", {})
                         .get("new", defaults[stage]["Moderate"]["new"]))
            ttk.Label(frame, text=stage, width=34).grid(row=i + 1, column=0, sticky="w")

            var_curr = tk.DoubleVar(value=float(saved_cur))
            var_fut = tk.DoubleVar(value=float(saved_new))
            self.demand_vars_current[stage] = var_curr
            self.demand_vars_future[stage] = var_fut
            ttk.Entry(frame, textvariable=var_curr, width=15).grid(row=i + 1, column=1, padx=2)
            ttk.Entry(frame, textvariable=var_fut, width=15).grid(row=i + 1, column=2, padx=2)

        def save_and_close():
            updated = {}
            for stage in self.stages:
                updated[stage] = {
                    "Moderate": {
                        "current": float(self.demand_vars_current[stage].get()),
                        "new": float(self.demand_vars_future[stage].get())
                    }
                }
            self.fuel_cycle_demand_factors = updated
            messagebox.showinfo("Saved", "Demand factors updated successfully.")
            popup.destroy()

        def reset_to_defaults():
            for stage in self.stages:
                self.demand_vars_current[stage].set(defaults[stage]["Moderate"]["current"])
                self.demand_vars_future[stage].set(defaults[stage]["Moderate"]["new"])

        btns = ttk.Frame(popup)
        btns.pack(pady=10)
        ttk.Button(btns, text="Save & Close", command=save_and_close).pack(side="left", padx=5)
        ttk.Button(btns, text="Reset to Default", command=reset_to_defaults).pack(side="left", padx=5)
        ttk.Button(btns, text="Cancel", command=popup.destroy).pack(side="left", padx=5)
        footer_frame = ttk.Frame(popup)
        footer_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 10))

        ttk.Label(
            footer_frame,
            text="You can obtain demands based on process parameters using this tool:",
            wraplength=520, justify="left"
        ).pack(side="left")

        link = tk.Label(
            footer_frame,
            text="WISE Uranium – Nuclear Fuel Material Calculator",
            fg="blue", cursor="hand2", font=("Arial", 10, "underline")
        )
        link.pack(side="left", padx=(6, 0))

        def _open_nfcm(event=None):
            import webbrowser
            webbrowser.open("https://www.wise-uranium.org/nfcm.html")

        link.bind("<Button-1>", _open_nfcm)
        popup.grab_set()
        popup.wait_window()

    def simulate_and_plot_workforce(self, stage):
        import numpy as np
        import matplotlib.pyplot as plt
        from tkinter import messagebox

        combined_capacities = self.combine_current_and_future_capacities(
            self.current_total_capacities, self.future_capacities_cum
        )
        current_scenario = self.selected_current_scenario.get()
        future_scenario = self.selected_future_scenario.get()
        factor_current = self.fuel_cycle_demand_factors[stage][current_scenario]["current"]
        factor_new = self.fuel_cycle_demand_factors[stage][future_scenario]["new"]

        years = [2025, 2030, 2035, 2040, 2045, 2050]
        workforce_samples_per_year = {year: [] for year in years}
        config = self.workforce_config[stage]
        dist_type = config["distribution"].get()
        n_samples = self.num_simulations

        # Set defaults for safety
        low = high = mean = cov = std = None

        # --- Validation and sample params
        if dist_type == "Uniform":
            low = config["low"].get()
            high = config["high"].get()
            if high <= low:
                messagebox.showerror(
                    title="Invalid Input",
                    message=f"For {stage}, 'High' must be greater than 'Low' in Uniform distribution.",
                    parent=self
                )
                return
        elif dist_type == "Normal":
            mean = config["mean"].get()
            cov = config["cov"].get()
            if cov < 0:
                messagebox.showerror(
                    title="Invalid Input",
                    message=f"For {stage}, Coefficient of Variation (CoV) must be non-negative.",
                    parent=self
                )
                return
            std = mean * cov
        demand_list = {}
        for scenario, cap_pairs in combined_capacities.items():
            demand_list[scenario] = [
                ((curr / 1000) * 0.927 * factor_current +
                 (fut / 1000) * 0.927 * factor_new)
                for (curr, fut) in cap_pairs
            ]

        years = [2025, 2030, 2035, 2040, 2045, 2050]
        data_by_year = {year: [] for year in years}
        for scenario in demand_list:
            for i, year in enumerate(years):
                demand = demand_list[scenario][i]

                if dist_type == "Uniform":
                    samples = np.random.uniform(low, high, size=n_samples) * demand/1000
                elif dist_type == "Normal":
                    samples = np.random.normal(mean, std, size=n_samples) * demand/1000
                    samples = np.clip(samples, 0, None)
                else:
                    samples = np.zeros(n_samples)

                workforce_samples_per_year[year].extend(samples)
        # Plot
        plt.figure(figsize=(10, 6))
        plt.boxplot([workforce_samples_per_year[y] for y in years], labels=years, patch_artist=True, showmeans=True)
        plt.title(f"Simulated Workforce for {stage}", fontsize=16)
        plt.xlabel("Year", fontsize=16)
        plt.ylabel("Workforce (people)", fontsize=16)
        plt.grid(True)
        plt.tight_layout()
        # Set tick font sizes
        plt.xticks(fontsize=14)
        plt.yticks(fontsize=14)
        # plot Assumptions
        lines = ["Assumptions:"]
        f_cur = self.fuel_cycle_demand_factors[stage][current_scenario]["current"]
        f_new = self.fuel_cycle_demand_factors[stage][future_scenario]["new"]
        lines.append(f"Demand per GWa\u2091: current = {f_cur:,.0f} t, future = {f_new:,.0f} t")
        lines.append("All uranium assumed mined and processed in the U.S.")
        legend_text = "\n".join(lines)
        dummy = Line2D([], [], linestyle="none", label=legend_text)
        leg = plt.legend(
            handles=[dummy],
            loc="upper left",
            frameon=True,
            fontsize=12,
        )
        leg.get_frame().set_facecolor("white")
        leg.get_frame().set_alpha(0.5)
        leg.get_frame().set_edgecolor("black")
        plt.show()

    def combine_current_and_future_capacities(self, current_capacities, future_capacities):
        combined_capacities = {}

        # Parse current capacity strings like "2025: 1500 MW" into floats [1500.0, ...]
        current_cap_floats = [
            float(cap.split(': ')[1].split(' MW')[0])
            for cap in current_capacities
        ]

        for scenario, future_cap_list in future_capacities.items():
            if len(current_cap_floats) != len(future_cap_list):
                raise ValueError(
                    f"The number of years in current capacities does not match the future capacities for scenario: {scenario}"
                )

            # Return (current, future) tuples
            combined_capacities[scenario] = list(zip(current_cap_floats, future_cap_list))

        return combined_capacities

    def plot_uranium_ore(self):
        import matplotlib.pyplot as plt

        if not self.current_total_capacities or not self.future_capacities_cum:
            messagebox.showerror("Error",
                                 "Missing capacity data. Please ensure current and future capacities are loaded.")
            return

        current_scenario = self.selected_current_scenario.get()
        future_scenario = self.selected_future_scenario.get()

        factors_current = self.fuel_cycle_demand_factors["Uranium Ore (Mining)"][current_scenario]["current"]
        factors_new = self.fuel_cycle_demand_factors["Uranium Ore (Mining)"][future_scenario]["new"]

        combined_capacities = self.combine_current_and_future_capacities(
            self.current_total_capacities, self.future_capacities_cum
        )

        uranium_demand = {}
        for scenario, cap_pairs in combined_capacities.items():
            uranium_demand[scenario] = [
                ((curr / 1000) * 0.927 * factors_current +
                 (fut / 1000) * 0.927 * factors_new)
                for (curr, fut) in cap_pairs
            ]

        years = [2025, 2030, 2035, 2040, 2045, 2050]
        data_by_year = {year: [] for year in years}
        for scenario in uranium_demand:
            for i, year in enumerate(years):
                data_by_year[year].append(uranium_demand[scenario][i])
        demand_list = [data_by_year[year] for year in years]

        plt.figure(figsize=(10, 6))
        box = plt.boxplot(demand_list, labels=years, patch_artist=True, showmeans=True, meanline=True)
        colors = ['lightblue', 'lightgreen', 'lightcoral', 'lightyellow', 'lightpink', 'lightskyblue']
        for patch, color in zip(box['boxes'], colors):
            patch.set_facecolor(color)
        for mean in box['means']:
            mean.set(marker='o', color='red', markersize=6)
        legend_text = (
            f"Assumptions:\n"
            f"Demand per GWa\u2091: current = {factors_current:,.0f} t, future = {factors_new:,.0f} t\n"
            f"All uranium assumed mined and processed in the U.S.\n"
        )
        dummy = Line2D([], [], linestyle="none", label=legend_text)
        leg = plt.legend(
            handles=[dummy],
            loc="upper left",
            frameon=True,
            fontsize=12,
        )
        leg.get_frame().set_facecolor("white")
        leg.get_frame().set_alpha(0.5)
        leg.get_frame().set_edgecolor("black")
        plt.title("Uranium Ore Demand Over Time (Mining)", fontsize=18)
        plt.xlabel("Year", fontsize=16)
        plt.ylabel("Uranium Ore Demand (Tonnes)", fontsize=16)
        plt.tick_params(axis='both', which='major', labelsize=14)
        plt.grid(True)
        plt.show()

    def plot_u3o8(self):
        import matplotlib.pyplot as plt

        if not self.current_total_capacities or not self.future_capacities_cum:
            messagebox.showerror("Error",
                                 "Missing capacity data. Please ensure current and future capacities are loaded.")
            return

        combined_capacities = self.combine_current_and_future_capacities(
            self.current_total_capacities, self.future_capacities_cum
        )

        current_scenario = self.selected_current_scenario.get()
        future_scenario = self.selected_future_scenario.get()

        factor_current = self.fuel_cycle_demand_factors["U3O8 (Milling)"][current_scenario]["current"]
        factor_new = self.fuel_cycle_demand_factors["U3O8 (Milling)"][future_scenario]["new"]

        demand = {}
        for scenario, cap_pairs in combined_capacities.items():
            demand[scenario] = [
                ((curr / 1000) * 0.927 * factor_current +
                 (fut / 1000) * 0.927 * factor_new)
                for (curr, fut) in cap_pairs
            ]

        years = [2025, 2030, 2035, 2040, 2045, 2050]
        data_by_year = {year: [] for year in years}
        for scenario in demand:
            for i, year in enumerate(years):
                data_by_year[year].append(demand[scenario][i])
        demand_list = [data_by_year[year] for year in years]

        plt.figure(figsize=(10, 6))
        box = plt.boxplot(demand_list, labels=years, patch_artist=True, showmeans=True, meanline=True)
        colors = ['lightblue', 'lightgreen', 'lightcoral', 'lightyellow', 'lightpink', 'lightskyblue']
        for patch, color in zip(box['boxes'], colors):
            patch.set_facecolor(color)
        for mean in box['means']:
            mean.set(marker='o', color='red', markersize=6)
        legend_text = (
            f"Assumptions:\n"
            f"Demand per GWa\u2091: current = {factor_current:,.0f} t, future = {factor_new:,.0f} t\n"
            f"All uranium assumed mined and processed in the U.S.\n"
        )
        dummy = Line2D([], [], linestyle="none", label=legend_text)
        leg = plt.legend(
            handles=[dummy],
            loc="upper left",
            frameon=True,
            fontsize=12,
        )
        leg.get_frame().set_facecolor("white")
        leg.get_frame().set_alpha(0.5)
        leg.get_frame().set_edgecolor("black")
        plt.title("U₃O₈ Demand Over Time (Milling)", fontsize=18)
        plt.xlabel("Year", fontsize=16)
        plt.ylabel("U₃O₈ Demand (Tonnes)", fontsize=16)
        plt.tick_params(axis='both', which='major', labelsize=14)
        plt.grid(True)
        plt.show()

    def plot_uf6_nat(self):
        import matplotlib.pyplot as plt

        if not self.current_total_capacities or not self.future_capacities_cum:
            messagebox.showerror("Error",
                                 "Missing capacity data. Please ensure current and future capacities are loaded.")
            return

        combined_capacities = self.combine_current_and_future_capacities(
            self.current_total_capacities, self.future_capacities_cum
        )

        current_scenario = self.selected_current_scenario.get()
        future_scenario = self.selected_future_scenario.get()

        factor_current = self.fuel_cycle_demand_factors["UF6 (Natural) (Conversion)"][current_scenario]["current"]
        factor_new = self.fuel_cycle_demand_factors["UF6 (Natural) (Conversion)"][future_scenario]["new"]

        demand = {}
        for scenario, cap_pairs in combined_capacities.items():
            demand[scenario] = [
                ((curr / 1000) * 0.927 * factor_current +
                 (fut / 1000) * 0.927 * factor_new)
                for (curr, fut) in cap_pairs
            ]

        years = [2025, 2030, 2035, 2040, 2045, 2050]
        data_by_year = {year: [] for year in years}
        for scenario in demand:
            for i, year in enumerate(years):
                data_by_year[year].append(demand[scenario][i])
        demand_list = [data_by_year[year] for year in years]

        plt.figure(figsize=(10, 6))
        box = plt.boxplot(demand_list, labels=years, patch_artist=True, showmeans=True, meanline=True)
        colors = ['lightblue', 'lightgreen', 'lightcoral', 'lightyellow', 'lightpink', 'lightskyblue']
        for patch, color in zip(box['boxes'], colors):
            patch.set_facecolor(color)
        for mean in box['means']:
            mean.set(marker='o', color='red', markersize=6)
        legend_text = (
            f"Assumptions:\n"
            f"Demand per GWa\u2091: current = {factor_current:,.0f} t, future = {factor_new:,.0f} t\n"
            f"All uranium assumed mined and processed in the U.S.\n"
        )
        dummy = Line2D([], [], linestyle="none", label=legend_text)
        leg = plt.legend(
            handles=[dummy],
            loc="upper left",
            frameon=True,
            fontsize=12,
        )
        leg.get_frame().set_facecolor("white")
        leg.get_frame().set_alpha(0.5)
        leg.get_frame().set_edgecolor("black")
        plt.title("UF₆ (Natural) Demand Over Time (Conversion)", fontsize=18)
        plt.xlabel("Year", fontsize=16)
        plt.ylabel("UF₆ (Natural) Demand (Tonnes)", fontsize=16)
        plt.tick_params(axis='both', which='major', labelsize=14)
        plt.grid(True)
        plt.show()

    def plot_uf6_enriched(self):
        import matplotlib.pyplot as plt

        if not self.current_total_capacities or not self.future_capacities_cum:
            messagebox.showerror("Error",
                                 "Missing capacity data. Please ensure current and future capacities are loaded.")
            return

        combined_capacities = self.combine_current_and_future_capacities(
            self.current_total_capacities, self.future_capacities_cum
        )

        current_scenario = self.selected_current_scenario.get()
        future_scenario = self.selected_future_scenario.get()

        factor_current = self.fuel_cycle_demand_factors["UF6 (Enriched) (Enrichment)"][current_scenario]["current"]
        factor_new = self.fuel_cycle_demand_factors["UF6 (Enriched) (Enrichment)"][future_scenario]["new"]

        demand = {}
        for scenario, cap_pairs in combined_capacities.items():
            demand[scenario] = [
                ((curr / 1000) * 0.927 * factor_current +
                 (fut / 1000) * 0.927 * factor_new)
                for (curr, fut) in cap_pairs
            ]

        years = [2025, 2030, 2035, 2040, 2045, 2050]
        data_by_year = {year: [] for year in years}
        for scenario in demand:
            for i, year in enumerate(years):
                data_by_year[year].append(demand[scenario][i])
        demand_list = [data_by_year[year] for year in years]

        plt.figure(figsize=(10, 6))
        box = plt.boxplot(demand_list, labels=years, patch_artist=True, showmeans=True, meanline=True)
        colors = ['lightblue', 'lightgreen', 'lightcoral', 'lightyellow', 'lightpink', 'lightskyblue']
        for patch, color in zip(box['boxes'], colors):
            patch.set_facecolor(color)
        for mean in box['means']:
            mean.set(marker='o', color='red', markersize=6)
        legend_text = (
            f"Assumptions:\n"
            f"Demand per GWa\u2091: current = {factor_current:,.0f} t, future = {factor_new:,.0f} t\n"
            f"All uranium assumed mined and processed in the U.S.\n"
        )
        dummy = Line2D([], [], linestyle="none", label=legend_text)
        leg = plt.legend(
            handles=[dummy],
            loc="upper left",
            frameon=True,
            fontsize=12,
        )
        leg.get_frame().set_facecolor("white")
        leg.get_frame().set_alpha(0.5)
        leg.get_frame().set_edgecolor("black")
        plt.title("UF₆ (Enriched) Demand Over Time (Enrichment)", fontsize=18)
        plt.xlabel("Year", fontsize=16)
        plt.ylabel("UF₆ (Enriched) Demand (Tonnes)", fontsize=16)
        plt.tick_params(axis='both', which='major', labelsize=14)
        plt.grid(True)
        plt.show()

    def plot_uo2(self):
        import matplotlib.pyplot as plt

        if not self.current_total_capacities or not self.future_capacities_cum:
            messagebox.showerror("Error",
                                 "Missing capacity data. Please ensure current and future capacities are loaded.")
            return

        combined_capacities = self.combine_current_and_future_capacities(
            self.current_total_capacities, self.future_capacities_cum
        )

        current_scenario = self.selected_current_scenario.get()
        future_scenario = self.selected_future_scenario.get()

        factor_current = self.fuel_cycle_demand_factors["UO2 (Fuel Fabrication)"][current_scenario]["current"]
        factor_new = self.fuel_cycle_demand_factors["UO2 (Fuel Fabrication)"][future_scenario]["new"]

        demand = {}
        for scenario, cap_pairs in combined_capacities.items():
            demand[scenario] = [
                ((curr / 1000) * 0.927 * factor_current +
                 (fut / 1000) * 0.927 * factor_new)
                for (curr, fut) in cap_pairs
            ]

        years = [2025, 2030, 2035, 2040, 2045, 2050]
        data_by_year = {year: [] for year in years}
        for scenario in demand:
            for i, year in enumerate(years):
                data_by_year[year].append(demand[scenario][i])
        demand_list = [data_by_year[year] for year in years]

        plt.figure(figsize=(10, 6))
        box = plt.boxplot(demand_list, labels=years, patch_artist=True, showmeans=True, meanline=True)
        colors = ['lightblue', 'lightgreen', 'lightcoral', 'lightyellow', 'lightpink', 'lightskyblue']
        for patch, color in zip(box['boxes'], colors):
            patch.set_facecolor(color)
        for mean in box['means']:
            mean.set(marker='o', color='red', markersize=6)
        legend_text = (
            f"Assumptions:\n"
            f"Demand per GWa\u2091: current = {factor_current:,.0f} t, future = {factor_new:,.0f} t\n"
            f"All uranium assumed mined and processed in the U.S.\n"
        )
        dummy = Line2D([], [], linestyle="none", label=legend_text)
        leg = plt.legend(
            handles=[dummy],
            loc="upper left",
            frameon=True,
            fontsize=12,
        )
        leg.get_frame().set_facecolor("white")
        leg.get_frame().set_alpha(0.5)
        leg.get_frame().set_edgecolor("black")
        plt.title("UO₂ Demand Over Time (Fuel Fabrication)", fontsize=18)
        plt.xlabel("Year", fontsize=16)
        plt.ylabel("UO₂ Demand (Tonnes)", fontsize=16)
        plt.tick_params(axis='both', which='major', labelsize=14)
        plt.grid(True)
        plt.show()

    def simulate_and_plot_total_workforce(self):
        import numpy as np
        import matplotlib.pyplot as plt
        from tkinter import messagebox

        if not self.current_total_capacities or not self.future_capacities_cum:
            messagebox.showerror(
                "Error",
                "Missing capacity data. Please ensure current and future capacities are loaded.",
                parent=self
            )
            return
        if not hasattr(self, "stages") or not self.stages:
            messagebox.showerror("Error", "No stages configured.", parent=self)
            return

        # Combine capacities and get scenarios
        combined_capacities = self.combine_current_and_future_capacities(
            self.current_total_capacities, self.future_capacities_cum
        )

        current_scenario =  "Moderate"
        future_scenario =  "Moderate"

        # Validate that demand factors exist for all stages
        missing = []
        for stage in self.stages:
            try:
                _ = self.fuel_cycle_demand_factors[stage][current_scenario]["current"]
                _ = self.fuel_cycle_demand_factors[stage][future_scenario]["new"]
            except Exception:
                missing.append(stage)
        if missing:
            messagebox.showerror(
                "Error",
                "Missing demand factors for stages: " + ", ".join(missing),
                parent=self
            )
            return

        years = [2025, 2030, 2035, 2040, 2045, 2050]
        n_samples = int(self.num_simulations) if getattr(self, "num_simulations", None) else 1000

        # Validate inputs per stage
        def _get_stage_sampling_params(stage):
            cfg = self.workforce_config[stage]
            dist = cfg["distribution"].get()
            if dist == "Uniform":
                low = cfg["low"].get()
                high = cfg["high"].get()
                if high <= low:
                    raise ValueError(f"For '{stage}', Uniform: 'High' must be greater than 'Low'.")
                return dist, (float(low), float(high))
            elif dist == "Normal":
                mean = cfg["mean"].get()
                cov = cfg["cov"].get()
                if cov < 0:
                    raise ValueError(f"For '{stage}', Normal: CoV must be non-negative.")
                std = float(mean) * float(cov)
                return dist, (float(mean), float(std))
            else:
                raise ValueError(f"Unknown distribution '{dist}' for '{stage}'.")

        try:
            stage_params = {stage: _get_stage_sampling_params(stage) for stage in self.stages}
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e), parent=self)
            return

        # Collect total workforce samples by year across all scenarios
        workforce_samples_per_year = {year: [] for year in years}

        for scenario, cap_pairs in combined_capacities.items():
            if len(cap_pairs) != len(years):
                messagebox.showerror(
                    "Error",
                    f"Capacity list length mismatch for scenario '{scenario}'.",
                    parent=self
                )
                return

            for i, year in enumerate(years):
                curr_cap, fut_cap = cap_pairs[i]

                # Start with zeros and add each stage's samples
                total_samples = np.zeros(n_samples, dtype=float)

                for stage in self.stages:
                    # Demand per stage for this year
                    f_cur = self.fuel_cycle_demand_factors[stage][current_scenario]["current"]
                    f_new = self.fuel_cycle_demand_factors[stage][future_scenario]["new"]
                    demand = ((curr_cap / 1000.0) * 0.927 * f_cur +
                              (fut_cap / 1000.0) * 0.927 * f_new)

                    dist, params = stage_params[stage]
                    if dist == "Uniform":
                        low, high = params
                        samples = np.random.uniform(low/1000, high/1000, size=n_samples)
                    else:  # Normal
                        mean, std = params
                        samples = np.random.normal(mean/1000, std, size=n_samples)
                        samples = np.clip(samples, 0, None)  # no negative workforce

                    # Scale by demand for this stage/year
                    total_samples += samples * demand

                # Add to the year pool across scenarios
                workforce_samples_per_year[year].extend(total_samples.tolist())

        # Plot the boxplot for totals
        plt.figure(figsize=(10, 6))
        plt.boxplot([workforce_samples_per_year[y] for y in years],
                    labels=years, patch_artist=True, showmeans=True)
        plt.title("Total Fuel Cycle Workforce (sum across stages)", fontsize=18)
        plt.xlabel("Year", fontsize=16)
        plt.ylabel("Workforce (people)", fontsize=16)
        # Force larger tick labels
        plt.xticks(fontsize=16)
        plt.yticks(fontsize=16)


        plt.grid(True)
        plt.tight_layout()
        plt.show()

