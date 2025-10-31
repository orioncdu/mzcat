import streamlit as st # FIX 1: Must be imported as 'st' to use st.text_input
import folium
from folium.plugins import MeasureControl
import math # Import math for trigonometry
from streamlit_folium import st_folium # Needed to display the folium map in Streamlit

st.set_page_config(layout="wide", page_title="Wind Assessment Map")
st.title("Wind Assessment Map Generator")
st.markdown("Enter coordinates and roof height to generate the AS1170.2 influence zone.")

# Copy and paste the Latitude, and Longitude from Google Maps here
CENTER_COORDS_str = st.text_input("Enter the center coordinates (Latitude,Longitude): ")

# --- Configuration ---
z_str = st.text_input("Enter the average roof height of the structure (m): ")

# --- Safety Guard to prevent crash on initial load (when inputs are empty) ---
if CENTER_COORDS_str and z_str:
    try:
        # Split the input string and convert to a tuple of floats
        CENTER_COORDS = tuple(map(float, CENTER_COORDS_str.split(',')))
        
        # Convert the input string to a float
        z = float(z_str) 
        
        LAG_DISTANCE_METERS = 20*z # Fig. 4.1 AS1170.2
        st.info(f"Lag Distance: {LAG_DISTANCE_METERS:.1f}m")
        st.info(f"Averaging Distance: {max(500, 40*z):.1f}m")
        RADIUS_METERS = LAG_DISTANCE_METERS + max(500, 40*z) # Fig. 4.1 AS1170.2
        st.success(f"Total Assessment Radius: {RADIUS_METERS:.1f}m")

        OUTPUT_FILE = "radius_map.html"

        # --- Helper Function for Radial Lines (Geodesic Math) ---
        # Calculates a point on the Earth's surface a certain distance and bearing from another point.
        def calculate_endpoint(lat, lon, distance, bearing):
            """
            Calculates the destination point given a starting point, distance, and bearing.
            Uses the great-circle distance formula.
            """
            R = 6378137 # Earth's radius in meters

            # Convert degrees to radians
            lat_rad = math.radians(lat)
            lon_rad = math.radians(lon)
            bearing_rad = math.radians(bearing)

            # Calculate new latitude
            new_lat_rad = math.asin(
                math.sin(lat_rad) * math.cos(distance / R) +
                math.cos(lat_rad) * math.sin(distance / R) * math.cos(bearing_rad)
            )

            # Calculate new longitude
            new_lon_rad = lon_rad + math.atan2(
                math.sin(bearing_rad) * math.sin(distance / R) * math.cos(lat_rad),
                math.cos(distance / R) - math.sin(lat_rad) * math.sin(new_lat_rad)
            )

            # Convert back to degrees
            return (math.degrees(new_lat_rad), math.degrees(new_lon_rad))


        # --- Map Generation ---
        # 1. Create a base map centered on the specified coordinates.
        GOOGLE_SATELLITE_URL = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
        GOOGLE_SATELLITE_ATTR = 'Map data © Google'
        m = folium.Map(
            location=CENTER_COORDS,
            zoom_start=15, # Increased zoom slightly to focus on the center for assessment
            tiles=GOOGLE_SATELLITE_URL,
            attr=GOOGLE_SATELLITE_ATTR)

        # 2. Add the radius circle to the map (the large, partially transparent cyan area).
        folium.Circle(
            location=CENTER_COORDS,
            radius=RADIUS_METERS,
            color='red',
            fill=True,
            weight=2,
            fill_color='white',
            fill_opacity=0.0,
            popup=f'Assessment Zone ({max(500, 40*z)}m)',
            name='Assessment Zone'
        ).add_to(m)

        # 3. Add an opaque blue circle on top of the lag distance zone to mask it.
        # This makes the lag zone appear blue and separates it from the outer cyan fill.
        folium.Circle(
            location=CENTER_COORDS,
            radius=LAG_DISTANCE_METERS,
            color='white',
            fill=True,
            weight=0, # No border needed for this fill
            fill_color='white',
            fill_opacity=0.3,
            # FIX: Assign the popup here since this is the clickable filled area that covers the center!
            popup=f'Lag Distance Zone ({LAG_DISTANCE_METERS:.1f}m)',
            name='Lag Zone Mask'
        ).add_to(m)

        # 3b. Add the lag distance circle border on top.
        folium.Circle(
            location=CENTER_COORDS,
            radius=LAG_DISTANCE_METERS,
            color='cyan',
            weight=1,
            fill=False, # Crucial: Must be False so the blue fill from 3 is visible
            # Removed popup here as it is redundant and likely obscured by the filled circle in step 3.
            name='Lag Distance Border'
        ).add_to(m)

        # 3c. Add 100m interval rings between Lag Distance and Total Radius
        current_radius = LAG_DISTANCE_METERS + 100
        while current_radius < RADIUS_METERS:
            # Ensure we don't draw a ring exactly on the outer boundary (which is already drawn in step 2)
            if current_radius < RADIUS_METERS - 10:
                folium.Circle(
                    location=CENTER_COORDS,
                    radius=current_radius,
                    color='white',
                    weight=1,
                    fill=False,
                    opacity=1,
                    dash_array='5, 5', # Dashed line for intermediate rings
                    popup=f'100m Grid Ring ({current_radius:.0f}m from center)',
                    name=f'Grid Ring {current_radius:.0f}m'
                ).add_to(m)
            current_radius += 100


        # 4. Draw the 8 radial lines (dividers) AND add Direction Labels
        # The dividing lines need to be shifted by 22.5 degrees so that N (0 deg) is the center of a piece.
        # Dividing lines now start at 337.5 deg (360 - 22.5) and increment by 45 deg.
        DIVIDER_BEARINGS = [337.5, 22.5, 67.5, 112.5, 157.5, 202.5, 247.5, 292.5]

        # The sector centers (where the labels go) are now the cardinal directions.
        LABEL_BEARINGS = [0, 45, 90, 135, 180, 225, 270, 315] # N, NE, E, SE, S, SW, W, NW
        directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
        lat, lon = CENTER_COORDS

        # Using your adjusted label distance: 120% of the radius. This places labels slightly outside the circle edge.
        LABEL_DISTANCE = RADIUS_METERS * 1.2 # Adjusted to 120% to keep it close to the circle edge for better visual grouping

        for i in range(8):
            divider_bearing = DIVIDER_BEARINGS[i]
            direction = directions[i]
            label_bearing = LABEL_BEARINGS[i]

            # --- Draw Divider Line ---
            # Calculate the end point at the edge of the RADIUS_METERS circle
            end_lat, end_lon = calculate_endpoint(lat, lon, RADIUS_METERS, divider_bearing)

            # Define the coordinates for the line segment
            line_coords = [CENTER_COORDS, (end_lat, end_lon)]

            # Draw the line
            folium.PolyLine(
                locations=line_coords,
                color='white',
                weight=1.5,
                opacity=0.8,
                popup=f'Wind Direction Sector Boundary: {divider_bearing} degrees'
            ).add_to(m)

            # --- Add Direction Label Marker ---
            label_lat, label_lon = calculate_endpoint(lat, lon, LABEL_DISTANCE, label_bearing)

            # Create a simple icon with the direction text
            label_html = f'<div style="font-size: 14pt; color: yellow; text-shadow: 1px 1px 2px black;">{direction}</div>'

            folium.Marker(
                location=[label_lat, label_lon],
                icon=folium.DivIcon(html=label_html),
                tooltip=f'Wind Direction: {direction}'
            ).add_to(m)

        # 5. Add a marker at the center point for clarity.
        folium.Marker(
            location=CENTER_COORDS,
            tooltip='Circle Center',
            icon=folium.Icon(color='orange', icon='info-sign')
        ).add_to(m)

        # 6. Add mapping tools.
        m.add_child(MeasureControl())

        # 7. Saving and Displaying
        # m.save(OUTPUT_FILE) # Streamlit doesn't need to save a file to display the map

        # FIX 4: Use st_folium to render the map in the Streamlit app
        st_folium(m, height=600, width='100%')
    
    except ValueError:
        st.error("Please ensure coordinates are in 'Lat, Lon' format and height is a valid number.")
        st.stop() # Stop further execution on bad input

else:
    st.warning("Please enter both coordinates and height to generate the map.")
    
eof
