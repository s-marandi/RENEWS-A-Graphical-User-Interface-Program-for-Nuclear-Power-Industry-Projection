import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import re


# ============================================================
# Fuel Cycle Demand & Workforce UI
# ============================================================


class FuelCycleWindow(tk.Toplevel):
    """
    Top-level window for plotting fuel-cycle demand and workforce.

    - Consumes deterministic current capacities and stochastic advanced
      capacities (by type) to produce demand and workforce distributions
      over a fixed set of milestone years.
    - Advanced capacity samples are built from a detailed
      `future_capacity_by_type_cumulative` structure by mapping
      reactor categories to four ADV buckets (A–D).
    """

    # Advanced reactor buckets shown in UI and used in simulations
    ADV_TYPES: List[str] = ["A", "B", "C", "D"]

    # Mapping from reactor categories to ADV buckets
    REACTOR_TO_ADV: Dict[str, str] = {
        # Adv A = Triso based
        "High-Temperature Gas-Cooled Reactor": "A",
        "Fluoride-Salt-Cooled High-Temperature Reactor": "A",
        "Fast Microreactor": "A",
        # Adv B = Metallic
        "Sodium-Cooled Fast Reactor": "B",
        # Adv C = UO2
        "Pressurized Water Reactor": "C",
        "Light Water Reactor": "C",
        # Adv D =  Silicon carbide
        "Gas-Cooled Fast Reactor": "D",
    }

    # ---------------------------------------------------------
    # Constructor
    # ---------------------------------------------------------
    def __init__(
        self,
        parent: tk.Misc,
        selected_demand_level_var: tk.StringVar,
        current_capacities: Sequence[Any],
        future_capacities: Any,
        num_simulations: int,
        future_capacity_by_type_cumulative: Dict[Any, Any],
    ) -> None:
        """Initialize window, parse inputs, and wire up UI."""
        super().__init__(parent)
        self.title("Fuel Cycle Demand")
        self.overrideredirect(False)
        self.resizable(True, True)

        # Raw inputs
        self.current_total_capacities_raw: Sequence[Any] = current_capacities
        self.future_capacities_raw: Any = future_capacities
        self.num_simulations: int = num_simulations
        self.future_capacity_by_type_cumulative: Dict[Any, Any] = (
            future_capacity_by_type_cumulative
        )
        # self.geometry("1600x1200")
        # Start maximized where supported
        try:
            self.state("zoomed")
        except Exception:
            self.attributes("-zoomed", True)

        # Scenario selection (kept only for compatibility)
        self.selected_current_scenario = tk.StringVar(value="Moderate")
        self.selected_future_scenario = tk.StringVar(value="Moderate")

        # Current capacities are deterministic by design
        self._init_current_list: List[float] = self._normalize_current_list(
            self.current_total_capacities_raw
        )

        # Build A–D stochastic samples from cumulative-by-type source
        mapped_samples = self._adv_samples_from_type_cumulative()

        # Fallback to legacy parser only if mapping produced all zeros
        if self._all_zero_samples(mapped_samples):
            mapped_samples = self._init_adv_types_samples_from_future(
                self.future_capacities_raw
            )

        # Store stochastic advanced capacity samples (used for sims)
        self._init_adv_caps_samples: Dict[str, List[List[float]]] = mapped_samples

        # Deterministic representatives (means) for editor-only display
        self._init_adv_caps: Dict[str, List[float]] = self._samples_to_means(
            self._init_adv_caps_samples
        )

        # Optional deterministic overrides set by the editor (kept only for compatibility)
        # {"A":[..], "B":[..], "C":[..], "D":[..]}
        self.adv_caps_override: Optional[Dict[str, List[float]]] = None
        self.current_caps_override: Optional[List[float]] = None

        # Demand-per-GWa factors (initial values set to zero)
        self.fuel_cycle_demand_factors: Dict[str, Dict[str, Dict[str, float]]] = {
            "Mining": {
                "Moderate": {
                    "current": 0.0,
                    "A": 0.0,
                    "B": 0.0,
                    "C": 0.0,
                    "D": 0.0,
                }
            },
            "Milling": {
                "Moderate": {
                    "current": 0.0,
                    "A": 0.0,
                    "B": 0.0,
                    "C": 0.0,
                    "D": 0.0,
                }
            },
            "Conversion": {
                "Moderate": {
                    "current": 0.0,
                    "A": 0.0,
                    "B": 0.0,
                    "C": 0.0,
                    "D": 0.0,
                }
            },
            "Enrichment": {
                "Moderate": {
                    "current": 0.0,
                    "A": 0.0,
                    "B": 0.0,
                    "C": 0.0,
                    "D": 0.0,
                }
            },
            "Fuel Fabrication": {
                "Moderate": {
                    "current": 0.0,
                    "A": 0.0,
                    "B": 0.0,
                    "C": 0.0,
                    "D": 0.0,
                }
            },
            "Custom Stage 1": {
                "Moderate": {
                    "current": 0.0,
                    "A": 0.0,
                    "B": 0.0,
                    "C": 0.0,
                    "D": 0.0,
                }
            },
            "Custom Stage 2": {
                "Moderate": {
                    "current": 0.0,
                    "A": 0.0,
                    "B": 0.0,
                    "C": 0.0,
                    "D": 0.0,
                }
            },
            "Custom Stage 3": {
                "Moderate": {
                    "current": 0.0,
                    "A": 0.0,
                    "B": 0.0,
                    "C": 0.0,
                    "D": 0.0,
                }
            },
        }

        # Benchmark/example demand factors (used by "Load baseline assumption")
        base_adv = {"A": 143670.17, "B": 143670.17, "C": 143670.17, "D": 143670.17}
        self._example_fuel_cycle_demand_factors: Dict[
            str, Dict[str, Dict[str, float]]
        ] = {
            "Mining": {"Moderate": {"current": 104677.72, **base_adv}},
            "Milling": {
                "Moderate": {
                    "current": 236.41,
                    **{t: 324.48 for t in self.ADV_TYPES},
                }
            },
            "Conversion": {
                "Moderate": {
                    "current": 295.00,
                    **{t: 404.89 for t in self.ADV_TYPES},
                }
            },
            "Enrichment": {
                "Moderate": {
                    "current": 35.45,
                    **{t: 13.64 for t in self.ADV_TYPES},
                }
            },
            "Fuel Fabrication": {
                "Moderate": {
                    "current": 26.92,
                    **{t: 10.36 for t in self.ADV_TYPES},
                }
            },
            "Custom Stage 1": {
                "Moderate": {"current": 0.0, **{t: 0.0 for t in self.ADV_TYPES}}
            },
            "Custom Stage 2": {
                "Moderate": {"current": 0.0, **{t: 0.0 for t in self.ADV_TYPES}}
            },
            "Custom Stage 3": {
                "Moderate": {"current": 0.0, **{t: 0.0 for t in self.ADV_TYPES}}
            },
        }

        # External demand level variable (kept for compatibility)
        self.selected_demand_level_var: tk.StringVar = selected_demand_level_var
        if not self.selected_demand_level_var.get():
            self.selected_demand_level_var.set("Scenario 3")

        # ----- UI -----
        desc = ""
        ttk.Label(
            self,
            text="Fuel Cycle Overview",
            font=("Arial", 9, "bold"),
        ).pack(pady=5)
        ttk.Label(
            self,
            text=desc,
            wraplength=700,
            justify="left",
        ).pack(padx=5, pady=5)

        control_frame = ttk.Frame(self)
        control_frame.pack(pady=5)
        ttk.Button(
            control_frame,
            text="Enter Demand Factors (Current & Advanced A–D)",
            command=self.enter_demand_inputs,
        ).pack(side="left", padx=5)
        ttk.Button(
            control_frame,
            text="View Yearly Capacities (Current & Advanced A–D)",
            command=self.edit_yearly_capacities,
        ).pack(side="left", padx=5)

        stage_box = ttk.LabelFrame(self, text="Plot Demand by Stage")
        stage_box.pack(padx=5, pady=5, fill="x")
        scope_frame = ttk.Frame(stage_box)
        scope_frame.pack(padx=8, pady=(6, 2), fill="x")
        ttk.Label(
            scope_frame,
            text="Demand Plot Scope:",
            width=20,
            anchor="w",
        ).pack(side="left")
        self.plot_scope = tk.StringVar(value="sum")  # current/future/sum
        ttk.Radiobutton(
            scope_frame,
            text="Current only",
            value="current",
            variable=self.plot_scope,
        ).pack(side="left", padx=6)
        ttk.Radiobutton(
            scope_frame,
            text="Advanced only",
            value="future",
            variable=self.plot_scope,
        ).pack(side="left", padx=6)
        ttk.Radiobutton(
            scope_frame,
            text="Sum",
            value="sum",
            variable=self.plot_scope,
        ).pack(side="left", padx=6)

        ttk.Separator(stage_box, orient="horizontal").pack(
            fill="x",
            padx=8,
            pady=(2, 6),
        )
        ttk.Button(
            stage_box,
            text="Plot Mining Demand",
            command=self.plot_uranium_ore,
        ).pack(pady=2, fill="x")
        ttk.Button(
            stage_box,
            text="Plot Milling Demand",
            command=self.plot_u3o8,
        ).pack(pady=2, fill="x")
        ttk.Button(
            stage_box,
            text="Plot Conversion Demand",
            command=self.plot_uf6_nat,
        ).pack(pady=2, fill="x")
        ttk.Button(
            stage_box,
            text="Plot Enrichment Demand",
            command=self.plot_uf6_enriched,
        ).pack(pady=2, fill="x")
        ttk.Button(
            stage_box,
            text="Plot Fuel Fabrication Demand",
            command=self.plot_uo2,
        ).pack(pady=2, fill="x")
        # Buttons for three custom stages
        ttk.Button(
            stage_box,
            text="Plot Custom Stage 1 Demand",
            command=self.plot_custom1,
        ).pack(pady=2, fill="x")
        ttk.Button(
            stage_box,
            text="Plot Custom Stage 2 Demand",
            command=self.plot_custom2,
        ).pack(pady=2, fill="x")
        ttk.Button(
            stage_box,
            text="Plot Custom Stage 3 Demand",
            command=self.plot_custom3,
        ).pack(pady=2, fill="x")

        ttk.Label(
            self,
            text="Fuel Cycle Workforce Factors (people per unit demand)",
            font=("Arial", 9, "bold"),
        ).pack(pady=(5, 5))

        self.stages: List[str] = [
            "Mining",
            "Milling",
            "Conversion",
            "Enrichment",
            "Fuel Fabrication",
            "Custom Stage 1",
            "Custom Stage 2",
            "Custom Stage 3",
        ]

        self.workforce_config_current: Dict[str, Dict[str, Any]] = {}
        self.workforce_config_adv_types: Dict[str, Dict[str, Dict[str, Any]]] = {
            t: {} for t in self.ADV_TYPES
        }
        self._build_workforce_table()

        wf_ctrl = ttk.LabelFrame(self, text="Workforce Plotting")
        wf_ctrl.pack(padx=10, pady=8, fill="x")
        self.wf_mode = tk.StringVar(value="all")  # "current","future","sum","all"
        ttk.Label(
            wf_ctrl,
            text="Workforce Plot Mode:",
            width=20,
            anchor="w",
        ).pack(side="left")
        ttk.Radiobutton(
            wf_ctrl,
            text="Current",
            value="current",
            variable=self.wf_mode,
        ).pack(side="left", padx=4)
        ttk.Radiobutton(
            wf_ctrl,
            text="Advanced (All types)",
            value="future",
            variable=self.wf_mode,
        ).pack(side="left", padx=4)
        ttk.Radiobutton(
            wf_ctrl,
            text="Sum",
            value="sum",
            variable=self.wf_mode,
        ).pack(side="left", padx=4)
        ttk.Radiobutton(
            wf_ctrl,
            text="All",
            value="all",
            variable=self.wf_mode,
        ).pack(side="left", padx=4)

        per_stage = ttk.Frame(self)
        per_stage.pack(padx=10, pady=(2, 8), fill="x")
        ttk.Label(
            per_stage,
            text="Stage:",
            width=18,
            anchor="w",
        ).pack(side="left")
        self.wf_stage_var = tk.StringVar(value=self.stages[0])
        ttk.Combobox(
            per_stage,
            textvariable=self.wf_stage_var,
            values=self.stages,
            state="readonly",
            width=42,
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            per_stage,
            text="Plot Workforce for Stage",
            command=self._plot_workforce_stage_dispatch,
        ).pack(side="left", padx=4)

        ttk.Button(
            self,
            text="Plot Total Fuel Cycle Workforce",
            command=self._plot_workforce_total_dispatch,
        ).pack(pady=6)

        self.transient(parent)
        self.grab_set()
        self.focus_set()
        self.wait_window(self)

    # =========================
    # 3: Small helpers
    # =========================
    def _years(self) -> List[int]:
        """Return milestone years used across the UI and calculations."""
        return [2025, 2030, 2035, 2040, 2045, 2050]

    def _all_zero_samples(self, samples_dict: Dict[str, List[List[float]]]) -> bool:
        """Return True if every sample in every ADV type is zero (or empty)."""
        for t in self.ADV_TYPES:
            for year_samples in samples_dict.get(t, []):
                if any(abs(x) > 0 for x in year_samples):
                    return False
        return True

    def _normalize_current_list(self, lst: Sequence[Any]) -> List[float]:
        """Parse 'YYYY: <val> MW' entries into a clean float list by year."""
        years = self._years()
        out: List[float] = []
        try:
            for i, _ in enumerate(years):
                try:
                    s = lst[i]
                    out.append(float(str(s).split(": ")[1].split(" MW")[0]))
                except Exception:
                    out.append(0.0)
        except Exception:
            out = [0.0] * len(years)
        if len(out) != len(years):
            out = (out + [0.0] * len(years))[: len(years)]
        return out

    # =========================
    # 4:  parsing utilities
    # =========================
    def _parse_stringified_array(self, s: str) -> Optional[List[float]]:
        """
        Parse CSV/array([...])/[...] strings with optional 'MW' units.

        Returns a list of floats, or None if parsing fails.
        """
        st = s.strip()

        # CSV without brackets
        if "," in st and "[" not in st and "]" not in st:
            vals: List[float] = []
            for p in re.split(r"[,\s]+", st):
                if not p:
                    continue
                p2 = p.replace("MW", "").replace("mw", "")
                try:
                    vals.append(float(p2))
                except Exception:
                    return None
            return vals

        # array(...) wrapper
        if st.startswith("array(") and st.endswith(")"):
            st = st[len("array(") : -1].strip()

        # [ ... ] with or without units
        if st.startswith("[") and st.endswith("]"):
            inside = st[1:-1]
            vals = []
            for p in re.split(r"[,\s]+", inside):
                if not p:
                    continue
                p2 = p.replace("MW", "").replace("mw", "")
                try:
                    vals.append(float(p2))
                except Exception:
                    return None
            return vals

        return None

    def _to_samples_list(self, entry: Any) -> List[float]:
        """Normalize an entry to a list of floats (samples)."""
        if isinstance(entry, (list, tuple, np.ndarray)):
            try:
                return [float(x) for x in entry]
            except Exception:
                return [0.0]
        if isinstance(entry, str):
            parsed = self._parse_stringified_array(entry)
            if parsed is not None:
                return parsed
            try:
                return [
                    float(entry.replace("MW", "").replace("mw", "").strip())
                ]
            except Exception:
                return [0.0]
        if isinstance(entry, dict):
            for k in ("samples", "vals", "values", "array", "data"):
                if k in entry and isinstance(
                    entry[k], (list, tuple, np.ndarray)
                ):
                    try:
                        return [float(x) for x in entry[k]]
                    except Exception:
                        pass
            if "text" in entry and isinstance(entry["text"], str):
                parsed = self._parse_stringified_array(entry["text"])
                if parsed is not None:
                    return parsed
            try:
                return [float(entry)]
            except Exception:
                return [0.0]
        try:
            return [float(entry)]
        except Exception:
            return [0.0]

    def _shape_to_types_by_year(
        self,
        obj: Any,
        ny: int,
    ) -> Dict[str, List[List[float]]]:
        """
        Normalize various shapes to per-type-per-year sample lists.

        - If `obj` is a dict with A/B/C/D keys, treat as per-type sequences.
        - If `obj` is a list/array, assign to type A, zeros for others.
        """
        if isinstance(obj, dict) and all(t in obj for t in self.ADV_TYPES):
            out: Dict[str, List[List[float]]] = {}
            for t in self.ADV_TYPES:
                seq = (
                    list(obj[t])
                    if isinstance(obj[t], (list, tuple, np.ndarray))
                    else [0.0] * ny
                )
                if len(seq) < ny:
                    seq += [0.0] * (ny - len(seq))
                seq = seq[:ny]
                out[t] = [self._to_samples_list(seq[i]) for i in range(ny)]
            return out
        if isinstance(obj, (list, tuple, np.ndarray)):
            per_year = list(obj)
            if len(per_year) < ny:
                per_year += [0.0] * (ny - len(per_year))
            per_year = per_year[:ny]
            return {
                "A": [
                    self._to_samples_list(per_year[i]) for i in range(ny)
                ],
                "B": [[0.0] for _ in range(ny)],
                "C": [[0.0] for _ in range(ny)],
                "D": [[0.0] for _ in range(ny)],
            }
        return {t: [[0.0] for _ in range(ny)] for t in self.ADV_TYPES}

    def _init_adv_types_samples_from_future(
        self,
        future_capacities: Any,
    ) -> Dict[str, List[List[float]]]:
        """Entry point to normalize `future_capacities` shape."""
        years = self._years()
        ny = len(years)
        return self._shape_to_types_by_year(future_capacities, ny)

    # =========================
    # 5: Samples from cumulative-by-type
    # =========================
    def _adv_samples_from_type_cumulative(
        self,
    ) -> Dict[str, List[List[float]]]:
        """
        Aggregate capacity samples by ADV bucket from category structure.

        Each top-level key in `future_capacity_by_type_cumulative` is
        treated as a stochastic scenario. For each year, reactor-category
        capacities are summed into A/B/C/D using `REACTOR_TO_ADV`.
        Returns: {"A":[[samples per year],...], "B":[...], "C":[...], "D":[...]}
        """
        years = self._years()
        ny = len(years)
        out: Dict[str, List[List[float]]] = {
            t: [[] for _ in range(ny)] for t in self.ADV_TYPES
        }

        fc = self.future_capacity_by_type_cumulative
        if not isinstance(fc, dict) or not fc:
            return {t: [[0.0] for _ in range(ny)] for t in self.ADV_TYPES}

        for _scen_name, scen_dict in fc.items():
            if not isinstance(scen_dict, dict):
                continue
            for idx, y in enumerate(years):
                sums = {"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0}
                ydict = scen_dict.get(y, {})
                if isinstance(ydict, dict):
                    for reactor_cat, designs in ydict.items():
                        adv = self.REACTOR_TO_ADV.get(reactor_cat)
                        if not adv:
                            continue
                        try:
                            total = sum(
                                float(v) for v in (designs or {}).values()
                            )
                        except Exception:
                            total = 0.0
                        sums[adv] += total
                for t in self.ADV_TYPES:
                    out[t][idx].append(float(sums[t]))

        # Ensure non-empty sample arrays
        for t in self.ADV_TYPES:
            for i in range(ny):
                if not out[t][i]:
                    out[t][i] = [0.0]
        return out

    def _samples_to_means(
        self,
        samples_dict: Dict[str, List[List[float]]],
    ) -> Dict[str, List[float]]:
        """
        Compute deterministic means per year for each ADV type.

        Used only for capacity editor display; simulations use samples.
        """
        years = self._years()
        ny = len(years)
        out: Dict[str, List[float]] = {}
        for t in self.ADV_TYPES:
            arr: List[float] = []
            stream = samples_dict.get(t, [[0.0] for _ in range(ny)])
            for i in range(ny):
                s = stream[i] if i < len(stream) else [0.0]
                arr.append(float(np.mean(s)) if s else 0.0)
            out[t] = arr
        return out

    # =========================
    # 6: Deterministic vs stochastic accessors
    # =========================
    def _get_caps_by_type_deterministic(
        self,
    ) -> Tuple[List[float], Dict[str, List[float]]]:
        """Return deterministic series for current and ADV means ."""
        cur_source = (
            self.current_caps_override
            if self.current_caps_override is not None
            else self._init_current_list
        )
        adv_source = (
            self.adv_caps_override
            if self.adv_caps_override is not None
            else self._init_adv_caps
        )
        cur = self._normalize_current_list(
            [f"{y}: {cur_source[i]} MW" for i, y in enumerate(self._years())]
        )
        adv = {t: list(adv_source.get(t, [])) for t in self.ADV_TYPES}
        return cur, adv

    def _get_caps_by_type_samples(self) -> Dict[str, List[List[float]]]:
        """Return stochastic ADV capacity samples."""
        years = self._years()
        ny = len(years)
        if self.adv_caps_override is not None:
            adv: Dict[str, List[List[float]]] = {}
            for t in self.ADV_TYPES:
                vals = self.adv_caps_override.get(t, [0.0] * ny)
                adv[t] = [[float(vals[i])] for i in range(ny)]
            return adv
        return self._init_adv_caps_samples

    # =========================
    # 7: Capacity Display
    # =========================
    def edit_yearly_capacities(self) -> None:
        """Display yearly deterministic capacities in a read-only table."""
        years = self._years()
        cur_det, adv_det = self._get_caps_by_type_deterministic()

        win = tk.Toplevel(self)
        win.title("Yearly Capacities - Current & Advanced A–D")
        win.geometry("860x460")

        head = ttk.Frame(win)
        head.pack(fill="x", padx=10, pady=(10, 0))
        ttk.Label(
            head,
            text=(
                "These are deterministic representatives (means). "
                "This window reflects calculated values."
            ),
            wraplength=780,
            justify="left",
        ).pack(side="left")

        table = ttk.Frame(win)
        table.pack(fill="both", expand=True, padx=10, pady=8)
        ttk.Label(
            table,
            text="Year",
            width=10,
        ).grid(row=0, column=0, padx=4, pady=4)
        ttk.Label(
            table,
            text="Current (MW)",
            width=16,
        ).grid(row=0, column=1, padx=4)
        for j, t in enumerate(self.ADV_TYPES, start=2):
            ttk.Label(
                table,
                text=f"Adv {t} (MW)",
                width=16,
            ).grid(row=0, column=j, padx=4)

        for i, y in enumerate(years):
            ttk.Label(
                table,
                text=str(y),
            ).grid(row=i + 1, column=0, padx=4, pady=2, sticky="w")
            ttk.Label(
                table,
                text=f"{cur_det[i]:,.3f}",
                width=18,
                anchor="e",
                relief="sunken",
            ).grid(row=i + 1, column=1, padx=4, pady=2)
            for j, t in enumerate(self.ADV_TYPES, start=2):
                val = adv_det[t][i] if i < len(adv_det[t]) else 0.0
                ttk.Label(
                    table,
                    text=f"{val:,.3f}",
                    width=18,
                    anchor="e",
                    relief="sunken",
                ).grid(row=i + 1, column=j, padx=4, pady=2)

        btns = ttk.Frame(win)
        btns.pack(pady=8)
        ttk.Button(btns, text="Close", command=win.destroy).pack(
            side="left",
            padx=6,
        )

        win.grab_set()
        win.wait_window()

    # =========================
    # 8: Workforce UI
    # =========================
    def _build_workforce_table(self) -> None:
        """Construct the compact workforce configuration table."""
        frame = ttk.LabelFrame(
            self,
            text="Workforce Factors (people per 1000 tons)",
        )
        frame.pack(padx=10, pady=4, fill="x")

        ttk.Label(
            frame,
            text="Stage",
            width=32,
            anchor="w",
        ).grid(row=0, column=0, padx=(8, 4), pady=(6, 2))
        ttk.Label(
            frame,
            text="Current",
            anchor="center",
        ).grid(row=0, column=1, padx=4, pady=(6, 2))
        for j, t in enumerate(self.ADV_TYPES, start=2):
            ttk.Label(
                frame,
                text=f"Advanced {t}",
                anchor="center",
            ).grid(row=0, column=j, padx=4, pady=(6, 2))

        def make_cell(parent: ttk.Frame) -> Dict[str, Any]:
            """Make a row of distribution controls for a stage."""
            cell = ttk.Frame(parent)
            dist_var = tk.StringVar(value="Uniform")
            cb = ttk.Combobox(
                cell,
                textvariable=dist_var,
                values=["Uniform", "Normal"],
                state="readonly",
                width=10,
            )
            cb.grid(row=0, column=0, padx=(0, 4))
            low_var = tk.DoubleVar()
            high_var = tk.DoubleVar()
            mean_var = tk.DoubleVar()
            cov_var = tk.DoubleVar()
            low_l = ttk.Label(cell, text="Low:")
            low_e = ttk.Entry(cell, textvariable=low_var, width=6)
            high_l = ttk.Label(cell, text="High:")
            high_e = ttk.Entry(cell, textvariable=high_var, width=6)
            mean_l = ttk.Label(cell, text="Mean:")
            mean_e = ttk.Entry(cell, textvariable=mean_var, width=6)
            cov_l = ttk.Label(cell, text="CoV:")
            cov_e = ttk.Entry(cell, textvariable=cov_var, width=6)

            def update() -> None:
                """Toggle parameter fields based on selected distribution."""
                if dist_var.get() == "Uniform":
                    mean_l.grid_forget()
                    mean_e.grid_forget()
                    cov_l.grid_forget()
                    cov_e.grid_forget()
                    low_l.grid(row=0, column=1)
                    low_e.grid(row=0, column=2, padx=(2, 4))
                    high_l.grid(row=0, column=3)
                    high_e.grid(row=0, column=4, padx=(2, 0))
                else:
                    low_l.grid_forget()
                    low_e.grid_forget()
                    high_l.grid_forget()
                    high_e.grid_forget()
                    mean_l.grid(row=0, column=1)
                    mean_e.grid(row=0, column=2, padx=(2, 4))
                    cov_l.grid(row=0, column=3)
                    cov_e.grid(row=0, column=4, padx=(2, 0))

            cb.bind("<<ComboboxSelected>>", lambda _e: update())
            update()
            return {
                "cell": cell,
                "distribution": dist_var,
                "low": low_var,
                "high": high_var,
                "mean": mean_var,
                "cov": cov_var,
                "low_label": low_l,
                "low_entry": low_e,
                "high_label": high_l,
                "high_entry": high_e,
                "mean_label": mean_l,
                "mean_entry": mean_e,
                "cov_label": cov_l,
                "cov_entry": cov_e,
            }

        def set_defaults(store: Dict[str, Any], st: str) -> None:
            """Populate benchmark workforce parameters per stage."""
            if st == "Mining":
                store["low"].set(0.31)
                store["high"].set(0.47)
                store["mean"].set(0.4)
                store["cov"].set(0.11)
            elif st == "Milling":
                store["low"].set(76.0)
                store["high"].set(127.0)
                store["mean"].set(94.5)
                store["cov"].set(0.14)
            elif st == "Conversion":
                store["low"].set(19.0)
                store["high"].set(21.0)
                store["mean"].set(20.0)
                store["cov"].set(0.023)
            elif st == "Enrichment":
                store["low"].set(380.0)
                store["high"].set(490.0)
                store["mean"].set(440.0)
                store["cov"].set(0.063)
            elif st == "Fuel Fabrication":
                store["low"].set(500.0)
                store["high"].set(700.0)
                store["mean"].set(600.0)
                store["cov"].set(0.083)
            else:
                store["low"].set(0.0)
                store["high"].set(0.0)
                store["mean"].set(0.0)
                store["cov"].set(0.0)

        def zero_out(store: Dict[str, Any]) -> None:
            """Set all fields to zero for initial state."""
            store["low"].set(0.0)
            store["high"].set(0.0)
            store["mean"].set(0.0)
            store["cov"].set(0.0)

        for r, stage in enumerate(self.stages, start=1):
            ttk.Label(
                frame,
                text=f"People per 1000 tons {stage}",
                anchor="w",
            ).grid(
                row=r,
                column=0,
                sticky="w",
                padx=(8, 4),
                pady=3,
            )
            cur_store = make_cell(frame)
            cur_store["cell"].grid(
                row=r,
                column=1,
                padx=4,
                pady=3,
                sticky="w",
            )
            self.workforce_config_current[stage] = cur_store
            zero_out(cur_store)
            for j, t in enumerate(self.ADV_TYPES, start=2):
                st_cell = make_cell(frame)
                st_cell["cell"].grid(
                    row=r,
                    column=j,
                    padx=4,
                    pady=3,
                    sticky="w",
                )
                self.workforce_config_adv_types[t][stage] = st_cell
                zero_out(st_cell)

        # Button to Load baseline assumption for workforce values (zeros if not available)
        def _load_workforce_benchmark() -> None:
            for stage in self.stages:
                try:
                    set_defaults(self.workforce_config_current[stage], stage)
                except Exception:
                    s = self.workforce_config_current[stage]
                    zero_out(s)
                for t in self.ADV_TYPES:
                    try:
                        set_defaults(
                            self.workforce_config_adv_types[t][stage],
                            stage,
                        )
                    except Exception:
                        zero_out(self.workforce_config_adv_types[t][stage])

        ctrl_row = ttk.Frame(self)
        ctrl_row.pack(padx=10, pady=(2, 6), fill="x")
        ttk.Button(
            ctrl_row,
            text="Load baseline assumption",
            command=_load_workforce_benchmark,
        ).pack(side="left")

    # =========================
    # 9: Demand-factor editing
    # =========================
    def enter_demand_inputs(self) -> None:
        """Popup to edit per-stage demand factors for current and ADV A–D."""
        popup = tk.Toplevel(self)
        popup.title("Enter Demand per GWa\u2091")
        popup.geometry("980x520")

        stages = self.stages
        types = ["Current"] + [f"Adv {t}" for t in self.ADV_TYPES]

        def get_val(stage: str, key: str) -> float:
            """Helper to fetch existing factor with float conversion."""
            val = self.fuel_cycle_demand_factors.get(stage, {})
            val = val.get("Moderate", {}).get(key, 0.0)
            try:
                return float(val)
            except Exception:
                return 0.0

        vars_map: Dict[str, Dict[str, tk.DoubleVar]] = {
            stage: {"Current": tk.DoubleVar(value=get_val(stage, "current"))}
            for stage in stages
        }
        for stage in stages:
            for t in self.ADV_TYPES:
                vars_map[stage][f"Adv {t}"] = tk.DoubleVar(
                    value=get_val(stage, t)
                )

        frame = ttk.Frame(popup)
        frame.pack(padx=10, pady=5, fill="x")
        ttk.Label(
            frame,
            text="Stage",
            width=34,
        ).grid(row=0, column=0, sticky="w")
        for c, typ in enumerate(types, start=1):
            ttk.Label(
                frame,
                text=f"{typ} (tonnes)",
            ).grid(row=0, column=c)

        for r, stage in enumerate(stages, start=1):
            ttk.Label(
                frame,
                text=stage,
                width=34,
            ).grid(row=r, column=0, sticky="w")
            for c, typ in enumerate(types, start=1):
                ttk.Entry(
                    frame,
                    textvariable=vars_map[stage][typ],
                    width=12,
                ).grid(row=r, column=c, padx=2)

        def save_and_close() -> None:
            """Write updated demand factors back to model state."""
            updated: Dict[str, Dict[str, Dict[str, float]]] = {}
            for stage in stages:
                row: Dict[str, float] = {
                    "current": float(vars_map[stage]["Current"].get())
                }
                for t in self.ADV_TYPES:
                    row[t] = float(vars_map[stage][f"Adv {t}"].get())
                updated[stage] = {"Moderate": row}
            self.fuel_cycle_demand_factors = updated
            messagebox.showinfo(
                "Saved",
                "Demand factors updated successfully.",
            )
            popup.destroy()

        def reset_to_defaults() -> None:
            """Set all popup fields to zero without modifying stored values."""
            for stage in stages:
                vars_map[stage]["Current"].set(0.0)
                for t in self.ADV_TYPES:
                    vars_map[stage][f"Adv {t}"].set(0.0)

        # Load baseline assumption values and apply them to the model state
        def load_benchmark_scenario() -> None:
            examples = getattr(
                self,
                "_example_fuel_cycle_demand_factors",
                None,
            )
            updated: Dict[str, Dict[str, Dict[str, float]]] = {}
            for stage in stages:
                if examples and stage in examples:
                    row = examples[stage].get("Moderate", {})
                    # Update UI vars
                    vars_map[stage]["Current"].set(
                        float(row.get("current", 0.0))
                    )
                    for t in self.ADV_TYPES:
                        vars_map[stage][f"Adv {t}"].set(
                            float(row.get(t, 0.0))
                        )
                    # Mirror into model state
                    updated[stage] = {
                        "Moderate": {
                            "current": float(row.get("current", 0.0)),
                            **{
                                t: float(row.get(t, 0.0))
                                for t in self.ADV_TYPES
                            },
                        }
                    }
                else:
                    vars_map[stage]["Current"].set(0.0)
                    for t in self.ADV_TYPES:
                        vars_map[stage][f"Adv {t}"].set(0.0)
                    updated[stage] = {
                        "Moderate": {
                            "current": 0.0,
                            **{t: 0.0 for t in self.ADV_TYPES},
                        }
                    }
            # Immediately apply to ensure plots use non-zero factors
            self.fuel_cycle_demand_factors = updated
            messagebox.showinfo(
                "Loaded",
                "Values loaded and applied.",
            )

        btns = ttk.Frame(popup)
        btns.pack(pady=10)
        ttk.Button(
            btns,
            text="Save & Close",
            command=save_and_close,
        ).pack(side="left", padx=5)
        ttk.Button(
            btns,
            text="Reset to Default",
            command=reset_to_defaults,
        ).pack(side="left", padx=5)
        ttk.Button(
            btns,
            text="Load baseline assumption",
            command=load_benchmark_scenario,
        ).pack(side="left", padx=5)
        ttk.Button(
            btns,
            text="Cancel",
            command=popup.destroy,
        ).pack(side="left", padx=5)

        footer = ttk.Frame(popup)
        footer.pack(side="bottom", fill="x", padx=10, pady=(0, 10))
        ttk.Label(
            footer,
            text=(
                "You can obtain demands based on process parameters "
                "using this tool:"
            ),
            wraplength=520,
            justify="left",
        ).pack(side="left")
        link = tk.Label(
            footer,
            text="WISE Uranium - Nuclear Fuel Material Calculator",
            fg="blue",
            cursor="hand2",
            font=("Arial", 10, "underline"),
        )
        link.pack(side="left", padx=(6, 0))

        def _open_nfcm(_event: Any = None) -> None:
            import webbrowser

            webbrowser.open("https://www.wise-uranium.org/nfcm.html")

        link.bind("<Button-1>", _open_nfcm)

        popup.grab_set()
        popup.wait_window()

    # =========================
    # 10: Demand helpers
    # =========================
    def _factors_for_stage(
        self,
        stage: str,
    ) -> Tuple[float, Dict[str, float]]:
        """Return (current_factor, {ADV: factor}) for a given stage."""
        row = self.fuel_cycle_demand_factors[stage]["Moderate"]
        f_cur = float(row["current"])
        f_adv = {t: float(row.get(t, 0.0)) for t in self.ADV_TYPES}
        return f_cur, f_adv

    # =========================
    # 11: Workforce samplers
    # =========================
    def _get_stage_params_from(
        self,
        store: Dict[str, Dict[str, Any]],
        stage: str,
    ) -> Tuple[str, Tuple[float, float]]:
        """Extract distribution parameters for a stage from a cell store."""
        cfg = store[stage]
        dist = cfg["distribution"].get()
        if dist == "Uniform":
            low = cfg["low"].get()
            high = cfg["high"].get()
            if high < low:
                raise ValueError(
                    f"For '{stage}', Uniform: High must be greater than or "
                    f"equal to Low."
                )
            return dist, (float(low), float(high))
        if dist == "Normal":
            mean = cfg["mean"].get()
            cov = cfg["cov"].get()
            if cov < 0:
                raise ValueError(
                    f"For '{stage}', Normal: CoV must be non-negative."
                )
            std = float(mean) * float(cov)
            return dist, (float(mean), float(std))
        raise ValueError(f"Unknown distribution '{dist}' for '{stage}'.")

    def _sampler(
        self,
        dist: str,
        params: Tuple[float, float],
        size: int,
    ) -> np.ndarray:
        """Draw workforce-per-ton factors according to selected distribution."""
        if dist == "Uniform":
            low, high = params
            if high == low:
                return np.full(size, (low / 1000.0))
            return np.random.uniform(
                low / 1000.0,
                high / 1000.0,
                size=size,
            )
        mean, std = params
        base = mean / 1000.0
        sigma = std / 1000.0
        s = base + np.random.normal(0.0, sigma, size=size)
        return np.clip(s, 0, None)

    # =========================
    # 12: DEMAND plots
    # =========================
    def _plot_stage(
        self,
        stage_key: str,
        title_text: str,
        y_label: str,
    ) -> None:
        """Boxplot the demand distribution by year for a single stage."""
        years = self._years()
        f_cur, f_adv = self._factors_for_stage(stage_key)

        # Deterministic current capacity
        cur_det, _ = self._get_caps_by_type_deterministic()

        # Stochastic advanced samples
        adv_samples = self._get_caps_by_type_samples()

        # Current demand - scalar per year
        d_current = [
            (cur_det[i] / 1000.0) * 0.927 * f_cur for i in range(len(years))
        ]

        # Advanced demand - sum across types while preserving sample arrays
        d_adv_list_per_year: List[List[float]] = []
        for i in range(len(years)):
            lens = [
                len(adv_samples[t][i])
                for t in self.ADV_TYPES
                if t in adv_samples
            ]
            max_len = max(lens) if lens else 1
            year_sum = np.zeros(max_len, dtype=float)
            for t in self.ADV_TYPES:
                cap_vec = np.array(adv_samples[t][i], dtype=float)
                if len(cap_vec) == 0:
                    cap_vec = np.zeros(max_len, dtype=float)
                if len(cap_vec) < max_len:
                    cap_vec = np.pad(
                        cap_vec,
                        (0, max_len - len(cap_vec)),
                        mode="edge",
                    )
                d_t = (cap_vec / 1000.0) * 0.927 * f_adv[t]
                year_sum += d_t
            d_adv_list_per_year.append(year_sum.tolist())

        # Sum scope = deterministic current + advanced samples
        d_sum_list_per_year: List[List[float]] = []
        for i in range(len(years)):
            adv_vec = np.array(d_adv_list_per_year[i], dtype=float)
            d_sum_list_per_year.append((adv_vec + d_current[i]).tolist())

        scope = self.plot_scope.get()
        if scope == "current":
            data = [[d_current[i]] for i in range(len(years))]
            scope_label = "Current only"
        elif scope == "future":
            data = d_adv_list_per_year
            scope_label = "Advanced (A–D)"
        else:
            data = d_sum_list_per_year
            scope_label = "Sum of current and advanced"

        plt.figure(figsize=(10, 6))
        box = plt.boxplot(
            data,
            labels=years,
            patch_artist=True,
            showmeans=True,
            meanline=True,
        )
        colors = [
            "lightblue",
            "lightgreen",
            "lightcoral",
            "lightyellow",
            "lightpink",
            "lightskyblue",
        ]
        for patch, color in zip(box["boxes"], colors):
            patch.set_facecolor(color)
        for mean_line in box["means"]:
            mean_line.set(marker="o", color="red", markersize=6)

        plt.title(f"{title_text} ({scope_label})", fontsize=18)
        plt.xlabel("Year", fontsize=16)
        plt.ylabel(y_label, fontsize=16)
        plt.tick_params(axis="both", which="major", labelsize=14)
        plt.grid(True)
        plt.show()

    def plot_uranium_ore(self) -> None:
        """Plot Mining demand."""
        self._plot_stage(
            "Mining",
            "Mining yearly Demand",
            "Mining yearly Demand (Tonnes)",
        )

    def plot_u3o8(self) -> None:
        """Plot Milling demand."""
        self._plot_stage(
            "Milling",
            "Milling yearly Demand",
            "Milling yearly Demand (Tonnes)",
        )

    def plot_uf6_nat(self) -> None:
        """Plot Conversion demand."""
        self._plot_stage(
            "Conversion",
            "Conversion yearly Demand",
            "Conversion yearly Demand (Tonnes)",
        )

    def plot_uf6_enriched(self) -> None:
        """Plot Enrichment demand."""
        self._plot_stage(
            "Enrichment",
            "Enrichment yearly Demand",
            "Enrichment yearly Demand (Tonnes)",
        )

    def plot_uo2(self) -> None:
        """Plot Fuel Fabrication demand."""
        self._plot_stage(
            "Fuel Fabrication",
            "Fuel Fabrication yearly Demand",
            "Fuel Fabrication yearly Demand (Tonnes)",
        )

    # plotters for custom stages
    def plot_custom1(self) -> None:
        """Plot demand for Custom Stage 1."""
        self._plot_stage(
            "Custom Stage 1",
            "Custom Stage 1 yearly Demand",
            "Custom Stage 1 yearly Demand (Tonnes)",
        )

    def plot_custom2(self) -> None:
        """Plot demand for Custom Stage 2."""
        self._plot_stage(
            "Custom Stage 2",
            "Custom Stage 2 yearly Demand",
            "Custom Stage 2 yearly Demand (Tonnes)",
        )

    def plot_custom3(self) -> None:
        """Plot demand for Custom Stage 3."""
        self._plot_stage(
            "Custom Stage 3",
            "Custom Stage 3 yearly Demand",
            "Custom Stage 3 yearly Demand (Tonnes)",
        )

    # =========================
    # 13: WORKFORCE plots
    # =========================
    def _plot_workforce_stage_dispatch(self) -> None:
        """Dispatch to plot a single stage’s workforce with mode setting."""
        stage = self.wf_stage_var.get()
        self._simulate_and_plot_workforce_stage(
            stage,
            mode=self.wf_mode.get(),
        )

    def _plot_workforce_total_dispatch(self) -> None:
        """Dispatch to plot the total workforce across all stages."""
        self._simulate_and_plot_total_workforce(mode=self.wf_mode.get())

    def _simulate_and_plot_workforce_stage(
        self,
        stage: str,
        mode: str = "all",
    ) -> None:
        """
        Simulate and boxplot workforce for a single stage.

        - Current: deterministic capacity × sampled workforce factor.
        - Advanced: per-type capacity samples × per-type workforce samples.
        """
        years = self._years()
        f_cur, f_adv = self._factors_for_stage(stage)

        cur_det, _ = self._get_caps_by_type_deterministic()
        adv_samples = self._get_caps_by_type_samples()

        try:
            dist_cur, params_cur = self._get_stage_params_from(
                self.workforce_config_current,
                stage,
            )
            adv_params = {
                t: self._get_stage_params_from(
                    self.workforce_config_adv_types[t],
                    stage,
                )
                for t in self.ADV_TYPES
            }
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e), parent=self)
            return

        samples_by_mode: Dict[str, Dict[int, List[float]]] = {
            m: {y: [] for y in years} for m in ["current", "future", "sum"]
        }

        for i, y in enumerate(years):
            # Current: deterministic capacity with workforce uncertainty
            n_cur = 1000
            ppl_cur = self._sampler(dist_cur, params_cur, n_cur)
            d_cur_scalar = (cur_det[i] / 1000.0) * 0.927 * f_cur
            s_cur = ppl_cur * d_cur_scalar
            samples_by_mode["current"][y].extend(s_cur.tolist())

            # Advanced: capacity samples per type with workforce samples
            lens = [len(adv_samples[t][i]) for t in self.ADV_TYPES]
            max_len = max(lens) if lens else n_cur
            adv_total = np.zeros(max_len, dtype=float)
            for t in self.ADV_TYPES:
                cap_vec = np.array(adv_samples[t][i], dtype=float)
                if len(cap_vec) == 0:
                    cap_vec = np.zeros(max_len, dtype=float)
                if len(cap_vec) < max_len:
                    cap_vec = np.pad(
                        cap_vec,
                        (0, max_len - len(cap_vec)),
                        mode="edge",
                    )
                d_vec = (cap_vec / 1000.0) * 0.927 * f_adv[t]
                dist_t, par_t = self._get_stage_params_from(
                    self.workforce_config_adv_types[t],
                    stage,
                )
                ppl_t = self._sampler(dist_t, par_t, size=max_len)
                adv_total += ppl_t * d_vec

            samples_by_mode["future"][y].extend(adv_total.tolist())

            # Align lengths and sum
            if len(s_cur) < len(adv_total):
                s_cur = np.pad(
                    s_cur,
                    (0, len(adv_total) - len(s_cur)),
                    mode="edge",
                )
            elif len(adv_total) < len(s_cur):
                adv_total = np.pad(
                    adv_total,
                    (0, len(s_cur) - len(adv_total)),
                    mode="edge",
                )
            samples_by_mode["sum"][y].extend((s_cur + adv_total).tolist())

        def _plot_mode(m: str) -> None:
            """Internal helper to boxplot for a given mode."""
            plt.figure(figsize=(10, 6))
            data = [samples_by_mode[m][year] for year in years]
            plt.boxplot(
                data,
                labels=years,
                patch_artist=True,
                showmeans=True,
            )
            title_map = {
                "current": "Current",
                "future": "Advanced (All types)",
                "sum": "Sum",
            }
            plt.title(
                f"Workforce for {stage} - {title_map[m]}",
                fontsize=16,
            )
            plt.xlabel("Year")
            plt.ylabel("Workforce (people)")
            plt.grid(True)
            plt.tight_layout()
            plt.show()

        if mode == "all":
            for m in ["current", "future", "sum"]:
                _plot_mode(m)
        else:
            _plot_mode(mode)

    def _simulate_and_plot_total_workforce(
        self,
        mode: str = "all",
    ) -> None:
        """Simulate and boxplot total workforce across all stages."""
        years = self._years()
        adv_samples = self._get_caps_by_type_samples()
        cur_det, _ = self._get_caps_by_type_deterministic()

        # Validate inputs
        try:
            for st in self.stages:
                _ = self._get_stage_params_from(
                    self.workforce_config_current,
                    st,
                )
                for t in self.ADV_TYPES:
                    _ = self._get_stage_params_from(
                        self.workforce_config_adv_types[t],
                        st,
                    )
        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Missing or invalid inputs: {e}",
                parent=self,
            )
            return

        samples_by_mode: Dict[str, Dict[int, List[float]]] = {
            m: {y: [] for y in years} for m in ["current", "future", "sum"]
        }

        for i, y in enumerate(years):
            # Current
            n_cur = 1000
            total_cur = np.zeros(n_cur, dtype=float)
            for st in self.stages:
                f_cur, _ = self._factors_for_stage(st)
                d_cur = (cur_det[i] / 1000.0) * 0.927 * f_cur
                dist_c, par_c = self._get_stage_params_from(
                    self.workforce_config_current,
                    st,
                )
                total_cur += self._sampler(dist_c, par_c, n_cur) * d_cur

            # Advanced
            lens = [len(adv_samples[t][i]) for t in self.ADV_TYPES]
            max_len = max(lens) if lens else n_cur
            total_adv = np.zeros(max_len, dtype=float)
            for st in self.stages:
                _, f_adv = self._factors_for_stage(st)
                stage_sum = np.zeros(max_len, dtype=float)
                for t in self.ADV_TYPES:
                    cap_vec = np.array(adv_samples[t][i], dtype=float)
                    if len(cap_vec) == 0:
                        cap_vec = np.zeros(max_len, dtype=float)
                    if len(cap_vec) < max_len:
                        cap_vec = np.pad(
                            cap_vec,
                            (0, max_len - len(cap_vec)),
                            mode="edge",
                        )
                    d_vec = (cap_vec / 1000.0) * 0.927 * f_adv[t]
                    dist_t, par_t = self._get_stage_params_from(
                        self.workforce_config_adv_types[t],
                        st,
                    )
                    ppl_t = self._sampler(dist_t, par_t, size=max_len)
                    stage_sum += ppl_t * d_vec
                total_adv += stage_sum

            samples_by_mode["current"][y].extend(total_cur.tolist())

            if len(total_cur) < len(total_adv):
                total_cur = np.pad(
                    total_cur,
                    (0, len(total_adv) - len(total_cur)),
                    mode="edge",
                )
            elif len(total_adv) < len(total_cur):
                total_adv = np.pad(
                    total_adv,
                    (0, len(total_cur) - len(total_adv)),
                    mode="edge",
                )

            samples_by_mode["future"][y].extend(total_adv.tolist())
            samples_by_mode["sum"][y].extend(
                (total_cur + total_adv).tolist()
            )

        def _plot_mode(m: str) -> None:
            """Internal helper to boxplot for given aggregate mode."""
            plt.figure(figsize=(10, 6))
            data = [samples_by_mode[m][year] for year in years]
            plt.boxplot(
                data,
                labels=years,
                patch_artist=True,
                showmeans=True,
            )
            title_map = {
                "current": "Current",
                "future": "Advanced (All types)",
                "sum": "Sum",
            }
            plt.title(
                f"Total Fuel Cycle Workforce - {title_map[m]}",
            )
            plt.xlabel("Year")
            plt.ylabel("Workforce (people)")
            plt.grid(True)
            plt.tight_layout()
            plt.show()

        if mode == "all":
            for m in ["current", "future", "sum"]:
                _plot_mode(m)
        else:
            _plot_mode(mode)

    def simulate_and_plot_total_workforce(self) -> None:
        """Compatibility wrapper"""
        self._simulate_and_plot_total_workforce(mode=self.wf_mode.get())
