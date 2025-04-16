import pandas as pd
import streamlit as st
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class BuildingConfig:
    """Configuration for building parameters"""
    total_area: float = 630800  # sq ft
    exhibition_percent: float = 0.49
    old_building_percent: float = 0.78
    new_building_percent: float = 0.22
    total_site_energy: float = 176424575  # kBtu/year
    eui: float = 279.7  # kBtu/sq ft/year
    hvac_percent: float = 0.85
    lighting_percent: float = 0.05
    other_percent: float = 0.10
    current_led_percentage: float = 0.70
    new_building_efficiency_factor: float = 0.85
    fan_percent_of_hvac: float = 0.25


@dataclass
class InterventionConfig:
    """Configuration for intervention parameters"""
    hvac_rightsizing_factor: float = 0.30
    humidity_control_factor: float = 0.10
    vfd_factor: float = 0.40
    led_conversion_factor: float = 0.70
    window_upgrade_factor: float = 0.10


@dataclass
class CostFactors:
    """Configuration for cost calculation parameters"""
    elec_rate: float = 0.305  # $/kWh
    gas_rate: float = 2.51  # $/therm
    kbtu_to_kwh: float = 3.412
    kbtu_to_therm: float = 100
    co2_factor_elec: float = 0.0002628  # metric tons CO2 per kWh
    co2_factor_gas: float = 0.0001812  # metric tons CO2 per therm


class MFAEnergySavingsTool:
    def __init__(self, config: BuildingConfig, interventions_config: InterventionConfig):
        self.config = config
        self.interventions_config = interventions_config

        # Calculate derived properties
        self.exhibition_area = self.config.total_area * self.config.exhibition_percent
        self.old_building_area = self.exhibition_area * self.config.old_building_percent
        self.new_building_area = self.exhibition_area * self.config.new_building_percent

        # Calculate energy allocation
        self.calculate_energy_allocation()

        # Calculate end-use breakdown
        self.calculate_end_use_breakdown()

    def calculate_energy_allocation(self):
        """Calculate energy allocation accounting for new building efficiency"""
        self.exhibition_energy = self.config.total_site_energy * self.config.exhibition_percent

        effective_old_area = self.old_building_area
        effective_new_area = self.new_building_area * self.config.new_building_efficiency_factor
        total_effective_area = effective_old_area + effective_new_area

        self.old_building_energy = (self.exhibition_energy *
                                    (effective_old_area / total_effective_area))
        self.new_building_energy = (self.exhibition_energy *
                                    (effective_new_area / total_effective_area))

    def calculate_end_use_breakdown(self):
        # Old building breakdown
        self.old_building_hvac = self.old_building_energy * self.config.hvac_percent
        self.old_building_lighting = self.old_building_energy * self.config.lighting_percent
        self.old_building_other = self.old_building_energy * self.config.other_percent
        self.old_building_fan = self.old_building_hvac * self.config.fan_percent_of_hvac

        # New building breakdown
        self.new_building_hvac = self.new_building_energy * self.config.hvac_percent
        self.new_building_lighting = self.new_building_energy * self.config.lighting_percent
        self.new_building_other = self.new_building_energy * self.config.other_percent
        self.new_building_fan = self.new_building_hvac * self.config.fan_percent_of_hvac

        # Total breakdown
        self.total_hvac = self.old_building_hvac + self.new_building_hvac
        self.total_lighting = self.old_building_lighting + self.new_building_lighting
        self.total_other = self.old_building_other + self.new_building_other
        self.total_fan = self.old_building_fan + self.new_building_fan

    def calculate_baseline(self) -> Dict:
        """Calculate baseline metrics for the building"""
        effective_new_area = self.new_building_area * self.config.new_building_efficiency_factor
        old_building_eui = self.old_building_energy / self.old_building_area if self.old_building_area > 0 else 0
        new_building_eui = self.new_building_energy / self.new_building_area if self.new_building_area > 0 else 0

        return {
            'Total Area (sq ft)': self.config.total_area,
            'Exhibition Area (sq ft)': self.exhibition_area,
            'Old Building Exhibition Area (sq ft)': self.old_building_area,
            'New Building Exhibition Area (sq ft)': self.new_building_area,
            'Total Energy (kBtu/year)': self.config.total_site_energy,
            'Exhibition Energy (kBtu/year)': self.exhibition_energy,
            'Old Building Energy (kBtu/year)': self.old_building_energy,
            'New Building Energy (kBtu/year)': self.new_building_energy,
            'EUI (kBtu/sq ft/year)': self.config.eui,
            'New Building Efficiency Factor': self.config.new_building_efficiency_factor,
            'Effective New Building Area (sq ft)': effective_new_area,
            'Old Building EUI (kBtu/sq ft/year)': old_building_eui,
            'New Building EUI (kBtu/sq ft/year)': new_building_eui,
            'EUI Ratio (New/Old)': new_building_eui / old_building_eui if old_building_eui > 0 else 0
        }

    def calculate_savings(self, interventions: Dict) -> Dict:
        """Calculate energy savings based on intervention implementation percentages"""
        savings = {
            'hvac_rightsizing': self._calculate_hvac_rightsizing_savings(interventions),
            'humidity_control': self._calculate_humidity_control_savings(interventions),
            'vfd': self._calculate_vfd_savings(interventions),
            'led_conversion': self._calculate_led_conversion_savings(interventions),
            'window_upgrades': self._calculate_window_upgrade_savings(interventions)
        }

        # Calculate total savings with interaction adjustments
        hvac_savings = sum(savings[measure] for measure in ['hvac_rightsizing', 'humidity_control',
                                                            'vfd', 'window_upgrades'])
        lighting_savings = savings['led_conversion']

        # Cap HVAC savings at 95% of total HVAC energy
        hvac_savings = min(hvac_savings, 0.95 * self.total_hvac)
        total_savings = hvac_savings + lighting_savings

        # Calculate new energy metrics
        new_energy_use = self.config.total_site_energy - total_savings
        new_eui = new_energy_use / self.config.total_area
        percent_savings = (total_savings / self.config.total_site_energy) * 100

        return {
            'Individual Savings (kBtu/year)': savings,
            'Total Savings (kBtu/year)': total_savings,
            'New Energy Use (kBtu/year)': new_energy_use,
            'New EUI (kBtu/sq ft/year)': new_eui,
            'Percent Savings': percent_savings,
            'Baseline EUI (kBtu/sq ft/year)': self.config.eui
        }

    def _calculate_hvac_rightsizing_savings(self, interventions: Dict) -> float:
        """Calculate savings from HVAC Optimization"""
        if 'hvac_rightsizing' not in interventions:
            return 0

        old_impl = interventions['hvac_rightsizing'].get('old', 0) / 100.0
        new_impl = interventions['hvac_rightsizing'].get('new', 0) / 100.0

        return (self.old_building_hvac * self.interventions_config.hvac_rightsizing_factor * old_impl +
                self.new_building_hvac * self.interventions_config.hvac_rightsizing_factor * new_impl)

    def _calculate_humidity_control_savings(self, interventions: Dict) -> float:
        """Calculate savings from humidity control"""
        if 'humidity_control' not in interventions:
            return 0

        old_impl = interventions['humidity_control'].get('old', 0) / 100.0
        new_impl = interventions['humidity_control'].get('new', 0) / 100.0

        return (self.old_building_hvac * self.interventions_config.humidity_control_factor * old_impl +
                self.new_building_hvac * self.interventions_config.humidity_control_factor * new_impl)

    def _calculate_vfd_savings(self, interventions: Dict) -> float:
        """Calculate savings from VFD implementation"""
        if 'vfd' not in interventions:
            return 0

        old_impl = interventions['vfd'].get('old', 0) / 100.0
        new_impl = interventions['vfd'].get('new', 0) / 100.0

        return (self.old_building_fan * self.interventions_config.vfd_factor * old_impl +
                self.new_building_fan * self.interventions_config.vfd_factor * new_impl)

    def _calculate_led_conversion_savings(self, interventions: Dict) -> float:
        """Calculate savings from LED conversion"""
        if 'led_conversion' not in interventions:
            return 0

        old_impl = interventions['led_conversion'].get('old', 0) / 100.0
        new_impl = interventions['led_conversion'].get('new', 0) / 100.0

        # Adjust for already implemented LEDs
        old_effective_impl = max(0, old_impl - self.config.current_led_percentage)
        new_effective_impl = max(0, new_impl - self.config.current_led_percentage)

        return (self.old_building_lighting * self.interventions_config.led_conversion_factor * old_effective_impl +
                self.new_building_lighting * self.interventions_config.led_conversion_factor * new_effective_impl)

    def _calculate_window_upgrade_savings(self, interventions: Dict) -> float:
        """Calculate savings from window upgrades"""
        if 'window_upgrades' not in interventions:
            return 0

        old_impl = interventions['window_upgrades'].get('old', 0) / 100.0
        new_impl = interventions['window_upgrades'].get('new', 0) / 100.0

        return (self.old_building_hvac * self.interventions_config.window_upgrade_factor * old_impl +
                self.new_building_hvac * self.interventions_config.window_upgrade_factor * new_impl)

    def estimate_costs_and_payback(self, interventions: Dict, savings_results: Dict,
                                   cost_factors: CostFactors) -> Dict:
        """Estimate costs, savings, and payback period for interventions"""
        # Implementation costs (per sq ft)
        implementation_costs = {
            'hvac_rightsizing': {'old': 15.00, 'new': 10.00},
            'humidity_control': {'old': 5.00, 'new': 3.00},
            'vfd': {'old': 2.00, 'new': 1.50},
            'led_conversion': {'old': 8.00, 'new': 8.00},
            'window_upgrades': {'old': 25.00, 'new': 10.00}
        }

        # Energy source splits for each measure
        elec_gas_split = {
            'hvac_rightsizing': {'elec': 0.40, 'gas': 0.60},
            'humidity_control': {'elec': 0.30, 'gas': 0.70},
            'vfd': {'elec': 1.0, 'gas': 0.0},
            'led_conversion': {'elec': 1.0, 'gas': 0.0},
            'window_upgrades': {'elec': 0.25, 'gas': 0.75}
        }

        # Calculate energy and cost savings
        electricity_savings_kbtu = 0
        gas_savings_kbtu = 0

        for measure, savings in savings_results['Individual Savings (kBtu/year)'].items():
            if measure in elec_gas_split:
                electricity_savings_kbtu += savings * elec_gas_split[measure]['elec']
                gas_savings_kbtu += savings * elec_gas_split[measure]['gas']

        # Convert energy savings
        electricity_savings_kwh = electricity_savings_kbtu / cost_factors.kbtu_to_kwh
        gas_savings_therm = gas_savings_kbtu / cost_factors.kbtu_to_therm

        # Calculate financial savings
        electricity_cost_savings = electricity_savings_kwh * cost_factors.elec_rate
        gas_cost_savings = gas_savings_therm * cost_factors.gas_rate
        annual_cost_savings = electricity_cost_savings + gas_cost_savings

        # Calculate CO2 emissions reduction
        co2_reduction_elec = electricity_savings_kwh * cost_factors.co2_factor_elec
        co2_reduction_gas = gas_savings_therm * cost_factors.co2_factor_gas
        total_co2_reduction = co2_reduction_elec + co2_reduction_gas

        # Calculate implementation costs
        total_cost = 0
        for measure, details in implementation_costs.items():
            if measure in interventions:
                old_impl = interventions[measure].get('old', 0) / 100.0
                new_impl = interventions[measure].get('new', 0) / 100.0
                total_cost += (self.old_building_area * details['old'] * old_impl +
                               self.new_building_area * details['new'] * new_impl)

        # Calculate payback period
        simple_payback = total_cost / annual_cost_savings if annual_cost_savings > 0 else float('inf')

        return {
            'Annual Cost Savings ($)': annual_cost_savings,
            'Electricity Savings ($/year)': electricity_cost_savings,
            'Natural Gas Savings ($/year)': gas_cost_savings,
            'Implementation Cost Estimate ($)': total_cost,
            'Simple Payback (years)': simple_payback,
            'CO2 Reduction (metric tons/year)': total_co2_reduction,
            'Electricity CO2 Reduction (metric tons/year)': co2_reduction_elec,
            'Natural Gas CO2 Reduction (metric tons/year)': co2_reduction_gas
        }


def create_streamlit_app():
    st.set_page_config(page_title="MFA Boston Energy Savings Tool", layout="wide")
    st.title("MFA Boston Energy Savings Estimation Tool")

    # Initialize configurations
    building_config = BuildingConfig()
    interventions_config = InterventionConfig()
    cost_factors = CostFactors()

    mfa_tool = MFAEnergySavingsTool(building_config, interventions_config)

    # Display building information
    st.subheader("Building Information")
    baseline_data = mfa_tool.calculate_baseline()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Building Area", f"{baseline_data['Total Area (sq ft)']:,.0f} sq ft")
        st.metric("Old Building Exhibition Area", f"{baseline_data['Old Building Exhibition Area (sq ft)']:,.0f} sq ft")

    with col2:
        st.metric("Exhibition Space", f"{baseline_data['Exhibition Area (sq ft)']:,.0f} sq ft")
        st.metric("New Building Exhibition Area", f"{baseline_data['New Building Exhibition Area (sq ft)']:,.0f} sq ft")

    with col3:
        st.metric("Baseline Total Energy", f"{baseline_data['Total Energy (kBtu/year)']:,.0f} kBtu/year")
        st.metric("New Building Efficiency",
                  f"{(1 - building_config.new_building_efficiency_factor) * 100:.0f}% better")

    # Intervention selection
    st.subheader("Select Interventions")
    interventions = create_intervention_controls(mfa_tool)

    # Calculate and display results
    if interventions:
        savings_results = mfa_tool.calculate_savings(interventions)
        financial_results = mfa_tool.estimate_costs_and_payback(interventions, savings_results, cost_factors)

        display_results(mfa_tool, savings_results, financial_results)


def create_intervention_controls(mfa_tool: MFAEnergySavingsTool) -> Dict:
    """Create Streamlit controls for intervention selection"""
    interventions = {}

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "HVAC Optimization", "Humidity/Temperature Control", "VFDs", "LED Lighting", "Window Upgrades"
    ])

    # HVAC Rightsizing
    with tab1:
        st.write("""
                **HVAC System Optimization**

                Current system: Running at 100% capacity with poor humidity control.

                Intervention: Replace with properly sized, high-efficiency equipment.

                Expected Savings: 30% of HVAC energy use in areas where implemented.
                """)
        use_hvac = st.checkbox("Implement HVAC Optimization", value=True, key="use_hvac")
        if use_hvac:
            col1, col2 = st.columns(2)
            with col1:
                old_impl = st.slider("Old Building %", 0, 100, 75, key="hvac_old")
            with col2:
                new_impl = st.slider("New Building %", 0, 100, 25, key="hvac_new")
            interventions['hvac_rightsizing'] = {'old': old_impl, 'new': new_impl}

    # Humidity Control
    with tab2:
        st.write("""
                **Advanced Humidity Control**

                Current situation: Wide RH variations, especially in old building.

                Intervention: Dedicated humidity/temperature systems with advanced controls.

                Expected Savings: 10% of HVAC energy use in areas where implemented.
                """)
        use_humidity = st.checkbox("Implement Humidity Control", value=True, key="use_humidity")
        if use_humidity:
            col1, col2 = st.columns(2)
            with col1:
                old_impl = st.slider("Old Building %", 0, 100, 90, key="humidity_old")
            with col2:
                new_impl = st.slider("New Building %", 0, 100, 50, key="humidity_new")
            interventions['humidity_control'] = {'old': old_impl, 'new': new_impl}

    # VFDs
    with tab3:
        st.write("""
                **Variable Frequency Drives (VFDs)**

                Current fan operation: 100% capacity.

                Intervention: Add VFDs to modulate fan speed.

                Expected Savings: 40% of fan energy use (25% of HVAC) in areas where implemented.
                """)
        use_vfd = st.checkbox("Implement VFDs", value=True, key="use_vfd")
        if use_vfd:
            col1, col2 = st.columns(2)
            with col1:
                old_impl = st.slider("Old Building %", 0, 100, 80, key="vfd_old")
            with col2:
                new_impl = st.slider("New Building %", 0, 100, 40, key="vfd_new")
            interventions['vfd'] = {'old': old_impl, 'new': new_impl}

    # LED Lighting
    with tab4:
        st.write("""
                **LED Lighting Conversion**

                Current: Mix of lighting technologies.

                Intervention: Museum-grade LED conversion.

                Expected Savings: 70% of lighting energy use in areas where implemented.
                """)
        use_led = st.checkbox("Implement LED Lighting", value=True, key="use_led")
        if use_led:
            st.info(f"Note: {mfa_tool.config.current_led_percentage * 100:.0f}% LED already implemented")
            col1, col2 = st.columns(2)
            with col1:
                old_impl = st.slider("Old Building %", 0, 100, 95, key="led_old")
            with col2:
                new_impl = st.slider("New Building %", 0, 100, 60, key="led_new")
            interventions['led_conversion'] = {'old': old_impl, 'new': new_impl}

    # Window Upgrades
    with tab5:
        st.write("""
                **Window Upgrades**

                Current: Likely older, less efficient windows.

                Intervention: High-performance glazing or secondary glazing.

                Expected Savings: 10% of HVAC energy use in areas where implemented.
                """)
        use_windows = st.checkbox("Implement Window Upgrades", value=True, key="use_windows")
        if use_windows:
            col1, col2 = st.columns(2)
            with col1:
                old_impl = st.slider("Old Building %", 0, 100, 70, key="windows_old")
            with col2:
                new_impl = st.slider("New Building %", 0, 100, 0, key="windows_new")
            interventions['window_upgrades'] = {'old': old_impl, 'new': new_impl}

    return interventions


def display_results(mfa_tool: MFAEnergySavingsTool, savings_results: Dict, financial_results: Dict):
    """Display results in Streamlit"""
    st.subheader("Results")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Energy Savings",
                  f"{savings_results['Total Savings (kBtu/year)']:,.0f} kBtu/year",
                  f"{savings_results['Percent Savings']:.1f}%")
    with col2:
        st.metric("New EUI",
                  f"{savings_results['New EUI (kBtu/sq ft/year)']:.1f} kBtu/sq ft/year",
                  f"-{mfa_tool.config.eui - savings_results['New EUI (kBtu/sq ft/year)']:.1f}")
    with col3:
        st.metric("Annual Cost Savings",
                  f"${financial_results['Annual Cost Savings ($)']:,.0f}",
                  f"CO₂ Reduction: {financial_results['CO2 Reduction (metric tons/year)']:.1f} tons/year")

    st.metric("Simple Payback Period",
              f"{financial_results['Simple Payback (years)']:.1f} years",
              f"Est. Implementation Cost: ${financial_results['Implementation Cost Estimate ($)']:,.0f}")

    # Savings by measure chart
    st.subheader("Savings by Measure")
    measure_names = {
        'hvac_rightsizing': 'HVAC Optimization',
        'humidity_control': 'Humidity/Temperature Control',
        'vfd': 'VFDs',
        'led_conversion': 'LED Lighting',
        'window_upgrades': 'Window Upgrades'
    }

    chart_data = pd.DataFrame({
        'Measure': [measure_names[key] for key in savings_results['Individual Savings (kBtu/year)'].keys()],
        'Savings (kBtu/year)': list(savings_results['Individual Savings (kBtu/year)'].values())
    })
    st.bar_chart(chart_data.set_index('Measure'))

    # Detailed savings table
    st.subheader("Detailed Savings")
    savings_data = []
    for key, name in measure_names.items():
        savings = savings_results['Individual Savings (kBtu/year)'][key]
        percent = (savings / mfa_tool.config.total_site_energy) * 100
        savings_data.append({
            'Measure': name,
            'Energy Savings': f"{savings:,.0f} kBtu/year",
            'Percent of Total': f"{percent:.2f}%"
        })
    st.table(pd.DataFrame(savings_data))

    # EUI comparison chart
    st.subheader("EUI Comparison")
    eui_data = pd.DataFrame({
        'Building Type': ['MFA Current', 'MFA Projected', 'Typical Museum', 'High Performance Museum'],
        'EUI (kBtu/sq ft/year)': [
            mfa_tool.config.eui,
            savings_results['New EUI (kBtu/sq ft/year)'],
            215,  # Example values
            140  # Example values
        ]
    })
    st.bar_chart(eui_data.set_index('Building Type'))

    # Energy use comparison
    st.subheader("Energy Use Before and After")
    energy_data = pd.DataFrame({
        'Scenario': ['Baseline', 'After Interventions'],
        'Energy Use (kBtu/year)': [
            mfa_tool.config.total_site_energy,
            savings_results['New Energy Use (kBtu/year)']
        ]
    })
    st.bar_chart(energy_data.set_index('Scenario'))

    # Show assumptions
    st.subheader("Assumptions and Notes")
    st.write("""
    **Energy Use Breakdown:**
    - HVAC represents **85%** of total energy use  
    - Lighting represents **5%** of total energy use  
    - Other systems (plug loads, etc.) represent **10%**  
    - Fan energy is estimated at **25% of HVAC energy**  

    **Intervention Savings Factors:**
    - **HVAC System Optimization:** 30% savings on HVAC energy where implemented  
    - **Humidity/Temperature Control:** 10% savings on HVAC energy where implemented  
    - **VFDs on Fans:** 40% savings on fan energy where implemented  
    - **LED Lighting:** 70% savings on remaining non-LED lighting  
    - **Window Upgrades:** 10% savings on HVAC energy where implemented  

    **Cost & Emissions Assumptions:**
    - Electricity rate: **\$0.305 per kWh**  
    - Natural gas rate: **\$2.51 per therm**  
    - CO₂ emissions: **0.0002628 metric tons per kWh** (electricity), **0.0001812 per therm** (gas)  
    - Implementation costs are **rough estimates** and may vary in practice  

    **Limitations:**
    - Does not account for future energy price changes  
    - Savings estimates are based on **industry averages** (actual performance may vary)  
    - Payback period does not include maintenance or replacement costs  
    """)


if __name__ == "__main__":
    create_streamlit_app()

#Run this(Command Prompt): streamlit run C:\Users\Angy\OneDrive\Escritorio\Curso_Python\Lección_1\P1\MFA\Final_Model.py