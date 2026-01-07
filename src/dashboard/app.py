"""
Streamlit Dashboard for Layoff Tracker
"""
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import logging
from datetime import date, datetime, timedelta

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config.settings import settings
from src.storage.database import DatabaseManager
from src.storage.export import DataExporter

# Setup logging
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Layoff Tracker Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-title {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_db_manager():
    """Get cached database manager"""
    return DatabaseManager()


@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_layoffs(_db_manager, start_date=None, end_date=None):
    """Load layoff data with caching"""
    if start_date and end_date:
        return _db_manager.get_layoffs_by_date_range(start_date, end_date)
    return _db_manager.get_all_layoffs()


def convert_to_dataframe(layoffs):
    """Convert layoff objects to DataFrame"""
    data = [layoff.to_dict() for layoff in layoffs]
    df = pd.DataFrame(data)

    if not df.empty:
        df['layoff_date'] = pd.to_datetime(df['layoff_date'])
        df['scraped_at'] = pd.to_datetime(df['scraped_at'])

    return df


def main():
    """Main dashboard app"""

    # Title
    st.markdown('<h1 class="main-title">📊 Layoff Tracker Dashboard</h1>', unsafe_allow_html=True)
    st.markdown("---")

    # Initialize database
    db_manager = get_db_manager()

    # Sidebar filters
    st.sidebar.header("🔍 Filters")

    # Date range filter
    default_end = date.today()
    default_start = default_end - timedelta(days=365)  # Default to 1 year to show more data

    start_date = st.sidebar.date_input("Start Date", default_start)
    end_date = st.sidebar.date_input("End Date", default_end)

    # Load all data first to get source options
    with st.spinner("Loading data..."):
        all_layoffs = load_layoffs(db_manager, start_date, end_date)
    
    # Dynamically get all unique sources from the data
    unique_sources = sorted(set(l.source for l in all_layoffs if l.source))
    source_options = ["All Sources"] + unique_sources
    
    # Source filter with multiselect for more flexibility
    selected_sources = st.sidebar.multiselect(
        "Data Sources",
        options=unique_sources,
        default=unique_sources,  # All selected by default
        help="Select one or more data sources to filter"
    )
    
    # If no sources selected, show all
    if not selected_sources:
        selected_sources = unique_sources
    
    # Filter by selected sources
    layoffs = [l for l in all_layoffs if l.source in selected_sources]
    
    # Country filter
    unique_countries = sorted(set(l.country for l in layoffs if l.country))
    if unique_countries:
        selected_countries = st.sidebar.multiselect(
            "Countries",
            options=unique_countries,
            default=unique_countries,
            help="Select one or more countries to filter"
        )
        
        if selected_countries:
            layoffs = [l for l in layoffs if l.country in selected_countries]
    
    # Show filter summary
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Showing:** {len(layoffs):,} records")
    st.sidebar.markdown(f"**Sources:** {len(selected_sources)}/{len(unique_sources)}")

    # Convert to DataFrame
    df = convert_to_dataframe(layoffs)

    if df.empty:
        st.warning("No layoff data found for the selected criteria. Try adjusting the filters or run the scraper to collect data.")
        return

    # Summary statistics
    st.header("📈 Summary Statistics")

    col1, col2, col3, col4 = st.columns(4)

    total_records = len(df)
    total_companies = df['company_name'].nunique()
    total_affected = df['employees_affected'].sum()
    avg_per_company = df['employees_affected'].mean()

    col1.metric("Total Records", f"{total_records:,}")
    col2.metric("Unique Companies", f"{total_companies:,}")
    col3.metric("Total Affected", f"{int(total_affected):,}" if pd.notna(total_affected) else "N/A")
    col4.metric("Avg per Company", f"{int(avg_per_company):,}" if pd.notna(avg_per_company) else "N/A")

    st.markdown("---")

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Trends", "🏢 Top Companies", "🏭 Industries", "📋 Data Table"])

    with tab1:
        st.header("Layoff Trends Over Time")

        # Group by date
        df_date = df.groupby('layoff_date').agg({
            'employees_affected': 'sum',
            'company_name': 'count'
        }).reset_index()
        df_date.columns = ['Date', 'Employees Affected', 'Number of Companies']

        # Line chart
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=df_date['Date'],
            y=df_date['Employees Affected'],
            mode='lines+markers',
            name='Employees Affected',
            line=dict(color='#1f77b4', width=2),
            hovertemplate='<b>%{x}</b><br>Employees: %{y:,.0f}<extra></extra>'
        ))

        fig.update_layout(
            title='Layoffs Over Time',
            xaxis_title='Date',
            yaxis_title='Employees Affected',
            hovermode='x unified',
            template='plotly_white',
            height=500
        )

        st.plotly_chart(fig, width='stretch')

    with tab2:
        st.header("Top Companies by Layoffs")

        # Group by company
        df_company = df.groupby('company_name')['employees_affected'].sum().sort_values(ascending=False).head(20)

        fig = px.bar(
            x=df_company.values,
            y=df_company.index,
            orientation='h',
            title='Top 20 Companies by Total Layoffs',
            labels={'x': 'Employees Affected', 'y': 'Company'},
            color=df_company.values,
            color_continuous_scale='Blues'
        )

        fig.update_layout(
            template='plotly_white',
            height=600,
            yaxis={'categoryorder': 'total ascending'}
        )

        st.plotly_chart(fig, width='stretch')

    with tab3:
        st.header("Industry Breakdown")

        if 'industry' in df.columns and df['industry'].notna().any():
            # Group by industry
            df_industry = df.groupby('industry').agg({
                'employees_affected': 'sum',
                'company_name': 'count'
            }).sort_values('employees_affected', ascending=False)

            df_industry.columns = ['Total Layoffs', 'Number of Events']

            col1, col2 = st.columns(2)

            with col1:
                # Pie chart
                fig_pie = px.pie(
                    df_industry,
                    values='Total Layoffs',
                    names=df_industry.index,
                    title='Layoffs by Industry'
                )
                st.plotly_chart(fig_pie, use_container_width=True)

            with col2:
                # Bar chart
                fig_bar = px.bar(
                    df_industry,
                    x=df_industry.index,
                    y='Total Layoffs',
                    title='Total Layoffs by Industry',
                    labels={'x': 'Industry', 'Total Layoffs': 'Employees Affected'}
                )
                fig_bar.update_layout(
                    xaxis_tickangle=-45,
                    template='plotly_white'
                )
                st.plotly_chart(fig_bar, use_container_width=True)

            # Industry table
            st.subheader("Industry Details")
            st.dataframe(df_industry, width='stretch')
        else:
            st.info("No industry data available")

    with tab4:
        st.header("Layoff Data Table")

        # Search/filter
        col1, col2 = st.columns(2)

        with col1:
            search_company = st.text_input("Search Company")

        with col2:
            search_industry = st.text_input("Search Industry")

        # Apply filters
        filtered_df = df.copy()

        if search_company:
            filtered_df = filtered_df[
                filtered_df['company_name'].str.contains(search_company, case=False, na=False)
            ]

        if search_industry:
            filtered_df = filtered_df[
                filtered_df['industry'].str.contains(search_industry, case=False, na=False)
            ]

        # Display table
        display_columns = [
            'layoff_date',
            'company_name',
            'industry',
            'employees_affected',
            'source'
        ]

        st.dataframe(
            filtered_df[display_columns].sort_values('layoff_date', ascending=False),
            width='stretch',
            hide_index=True
        )

    # Data Export Section
    st.markdown("---")
    st.header("💾 Export Data")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Export to CSV", type="primary"):
            exporter = DataExporter()
            # Use currently filtered layoffs
            filepath = exporter.to_csv(layoffs)
            st.success(f"Exported to {filepath}")

    with col2:
        if st.button("Export to JSON"):
            exporter = DataExporter()
            filepath = exporter.to_json(layoffs)
            st.success(f"Exported to {filepath}")

    with col3:
        if st.button("Export to Excel"):
            exporter = DataExporter()
            filepath = exporter.to_excel(layoffs)
            st.success(f"Exported to {filepath}")

    # Footer
    st.markdown("---")
    st.markdown("""
        <div style='text-align: center; color: #666;'>
            <p>Layoff Tracker Dashboard | Data updated every 6 hours</p>
            <p>For questions or issues, please open an issue on GitHub</p>
        </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
