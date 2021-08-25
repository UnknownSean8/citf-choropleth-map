# Source:
# https://github.com/CITF-Malaysia/citf-public
# https://earthworks.stanford.edu/catalog/stanford-qg469kj1734
# https://simplemaps.com/data/my-cities

import requests
import branca.colormap as cm
import geopandas as gpd
import numpy as np
import pandas as pd
import time
import folium
import math

from folium import Marker
from folium.plugins import TimeSliderChoropleth, MarkerCluster
from io import StringIO

STATE_DATA_URL = "https://raw.githubusercontent.com/CITF-Malaysia/citf-public/main/vaccination/vax_state.csv"
STATE_POP_URL = "https://raw.githubusercontent.com/CITF-Malaysia/citf-public/main/static/population.csv"

def fetch_required_csv(data_url):
    return pd.read_csv(StringIO(requests.get(data_url).text))

def clean_and_merge(vaccinationData, populationData, malaysia_geoLoc, districts_full):
    # Vaccination data, for most recent date
    vaccinationData = vaccinationData.loc[:][["date", "state", "cumul_full"]]
    vaccinationData.reset_index(inplace = True)
    vaccinationData.loc[(vaccinationData.state == "W.P. Kuala Lumpur"), "state"] = "Kuala Lumpur"
    vaccinationData.loc[(vaccinationData.state == "W.P. Labuan"), "state"] = "Labuan"
    vaccinationData.loc[(vaccinationData.state == "W.P. Putrajaya"), "state"] = "Putrajaya"

    # Population data 
    populationData = populationData.loc[:][["state", "pop"]]
    populationData.loc[(populationData.state == "W.P. Kuala Lumpur"), "state"] = "Kuala Lumpur"
    populationData.loc[(populationData.state == "W.P. Labuan"), "state"] = "Labuan"
    populationData.loc[(populationData.state == "W.P. Putrajaya"), "state"] = "Putrajaya"
    populationData = populationData.drop(0)

    vacandpop = pd.merge(vaccinationData, populationData, on="state", how="left").drop(columns=["index"])

    filter_geo = malaysia_geoLoc.loc[(malaysia_geoLoc.capital == "admin") | (malaysia_geoLoc.capital == "primary")][["admin_name", "lat", "lng"]]

    # Vaccination and population data
    vaccinationAndPopulationByLocation = pd.merge(vacandpop, filter_geo, left_on='state',right_on='admin_name', how="left").drop(columns=["admin_name"])

    # Add state border
    districts_full = districts_full[['NAME_1', "geometry"]]
    districts_full.loc[(districts_full.NAME_1 == "Trengganu"), "NAME_1"] = "Terengganu"
    districts_full = districts_full.set_index("NAME_1")

    vaccinationAndPopulationByLocation = pd.merge(vaccinationAndPopulationByLocation, districts_full, left_on='state',right_on='NAME_1', how="left")

    # Calculate percentage vaccinated by state
    vaccinationAndPopulationByLocation["percent_vaccinated"] = vaccinationAndPopulationByLocation["cumul_full"] / vaccinationAndPopulationByLocation["pop"]

    vaccinationAndPopulationByLocation["cumul_full"] = vaccinationAndPopulationByLocation["cumul_full"] / 1000

    vaccinationAndPopulationByLocation['date'] = vaccinationAndPopulationByLocation['date'].astype(str)
    vaccinationAndPopulationByLocation['date'] = pd.to_datetime(vaccinationAndPopulationByLocation['date']).values.astype(np.int64) // 10 ** 9

    return vaccinationAndPopulationByLocation

def colour(df):
    max_colour = max(df["cumul_full"])
    min_colour = min(df["cumul_full"])
    cmap = cm.linear.YlOrRd_09.scale(min_colour, max_colour)
    df["colour"] = df["cumul_full"].map(cmap)

    return cmap

def create_style_dict(df):
    state_list = df["state"].unique().tolist()
    state_idx = range(len(state_list))

    style_dict = {}
    for i in state_idx:
        state = state_list[i]
        result = df[df['state'] == state]
        inner_dict = {}
        for _, r in result.iterrows():
            inner_dict[r['date']] = {'color': r['colour'], 'opacity': 0.7}
        style_dict[str(i)] = inner_dict

    return style_dict

def plot(df, style_dict, cmap):
    state_df = df[['geometry']]
    state_gdf = gpd.GeoDataFrame(state_df)
    state_gdf = state_gdf.drop_duplicates().reset_index()

    slider_map = folium.Map(location=[5, 101], zoom_start=6, max_bounds=True, tiles='cartodbpositron')
    folium.TileLayer('Stamen Terrain').add_to(slider_map)
    folium.TileLayer('Stamen Toner').add_to(slider_map)
    folium.TileLayer('Stamen Water Color').add_to(slider_map)
    folium.TileLayer('cartodbdark_matter').add_to(slider_map)

    _ = TimeSliderChoropleth(
        data=state_gdf.to_json(),
        styledict=style_dict,

    ).add_to(slider_map)

    _ = cmap.add_to(slider_map)

    mc = MarkerCluster()
    for idx, row in df.iterrows(): 
        if not math.isnan(row['lng']) and not math.isnan(row['lat']):
            mc.add_child(Marker(location=[row['lat'], row['lng']],
                                tooltip=str(round(row['percent_vaccinated']*100, 2))+"%"))
    slider_map.add_child(mc)

    folium.LayerControl().add_to(slider_map)

    cmap.caption = "Number of confirmed full vaccination x1000"

    slider_map.save(outfile='TimeSliderChoropleth.html')

if __name__ == "__main__":
    state_vac_data = fetch_required_csv(STATE_DATA_URL)
    state_pop_data = fetch_required_csv(STATE_POP_URL)
    state_location = pd.read_csv("MY_Geo.csv")
    state_geometry = gpd.read_file("data/MYS_adm1.shp")

    res = clean_and_merge(state_vac_data, state_pop_data, state_location, state_geometry)
    
    cmap = colour(res)

    style_dict = create_style_dict(res)

    plot(res, style_dict, cmap)

    

