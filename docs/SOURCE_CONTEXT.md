# NiñoRadar

### Satellite intelligence for understanding flood impacts

**Challenge:** Dancing with the SARs — NASA Space Apps Challenge 2026.

**Application area:** Disaster risk management, Earth observation, and geospatial intelligence.

**Pilot area:** Catacaos and Cura Mori, Piura, Peru.

**Primary technology:** Synthetic Aperture Radar (SAR) from the NASA–ISRO NISAR mission.

This is the English translation of the complete project narrative supplied by the owner. Its product commitments remain authoritative; the linked team document provides supplementary research. Translation replaces the Spanish working copy at the owner's request. Proper names and source URLs retain their original spelling.

## 1. The problem

Peru is highly vulnerable to extreme rainfall associated with coastal El Niño, particularly in regions such as Piura, where overflowing rivers and floods can affect homes, roads, agricultural land, and essential services.

During these events, a central challenge is understanding precisely how a flood is spreading, which parts of the territory may be affected, and which areas need priority assessment.

Although Peru has hydrological monitoring systems, risk maps, and emergency reporting mechanisms, information is distributed across platforms. These sources do not always make it possible to view observed changes on the ground alongside potentially exposed infrastructure.

Heavy cloud cover during rainfall also limits optical satellite imagery as a means of assessing surface conditions.

This creates a concrete need: **turn satellite observations of the land surface into accessible geospatial information that supports flood assessment**.

## 2. Our solution

**NiñoRadar** is a proposed interactive web platform that uses NISAR SAR imagery to detect changes in surface water extent, monitor flood evolution, and analyze possible impacts on infrastructure and communities.

Unlike conventional optical satellites, NISAR can observe the surface during the day or night and through cloud cover, making it particularly valuable during periods of heavy rainfall.

By analyzing imagery acquired on different dates, NiñoRadar identifies areas where new water accumulations appear and combines them with geographic information about roads, settlements, and agricultural land.

The platform turns these results into interactive maps and territorial indicators that address three fundamental questions:

1. **Where has water expanded?** Identify changes consistent with flooding relative to previous conditions.
2. **What might be affected?** Estimate which roads, buildings, and agricultural areas intersect the detected areas.
3. **Where should assessment be prioritized?** Identify sectors with a greater concentration of potentially exposed infrastructure to support field verification.

NiñoRadar aims to make complex scientific data understandable and useful to people involved in disaster risk management.

## 3. How NiñoRadar works

The proposed platform follows four stages.

### Stage 1: Satellite observation

Obtain NISAR SAR observations from different dates covering the same study area.

### Stage 2: Change detection

Process radar imagery to identify backscatter variations that may indicate the appearance or expansion of water bodies. Apply filtering and classification methods to produce preliminary flood maps.

### Stage 3: Territorial analysis

Intersect detected inundation surfaces with geographic layers describing infrastructure, roads, and land use to estimate possible exposure. Examine road connections that may be affected to identify settlements whose accessibility needs assessment.

### Stage 4: Visualization and decision support

Present results through an interactive web application that supports date comparisons, inspection of potentially affected areas, and geospatial reporting for territorial assessment.

## 4. Innovation

The main value of NiñoRadar is not simply detecting flooded surfaces, which is an established SAR remote-sensing application.

**The proposal connects satellite observation with territorial exposure analysis and the prioritization of field assessments.**

Hydrometeorological systems describe rainfall and river evolution. NiñoRadar would complement that information by showing where the observed surface has changed and which infrastructure spatially coincides with those changes.

The proposed differentiation has three components:

- **Observation through clouds:** use SAR to examine surface conditions when optical imagery is limited.
- **Territorial exposure analysis:** turn water maps into measurable estimates of potentially exposed infrastructure and agricultural land.
- **Geospatial prioritization:** identify sectors where detected exposure warrants verification, incorporating data quality and uncertainty indicators.

The solution is intended to complement official warning and damage-assessment systems.

## 5. Case study: Piura, Peru

Initial development focuses on Catacaos and Cura Mori in the Piura region, areas historically affected by floods associated with exceptional rainfall.

The region is a relevant case study because urban areas, agricultural land, and transport networks are exposed to flooding from the Piura River.

The prototype will examine changes in water extent between satellite observations and how these changes intersect elements of the territory.

The methodology could later be adapted to other vulnerable areas in Peru, including parts of the Rímac basin in Lima, subject to suitable SAR observations.

## 6. Potential beneficiaries

- **Municipalities and regional governments:** support identification of sectors requiring assessment.
- **Disaster risk management institutions, including INDECI and CENEPRED:** provide complementary geospatial information.
- **Humanitarian response teams:** understand potential exposure of access roads and settlements.
- **Researchers and communities:** understand how floods evolve and how the territory may be affected.

## 7. NASA Space Apps prototype

The intended hackathon prototype has three main capabilities:

1. **Flood detection map:** visualize changes between two comparable SAR observations.
2. **Infrastructure exposure map:** identify road segments and agricultural areas that intersect surfaces classified as inundated.
3. **Territorial assessment dashboard:** display detected area, potentially exposed infrastructure, and sectors proposed for verification.

The prototype will use georeferenced NISAR products when comparable acquisitions exist over the study area, together with open cartographic data. Historical Sentinel-1 imagery may support methodological validation and must be clearly identified as another mission.

Classification uncertainty and each observation's acquisition date must be documented. Results must not be presented as real-time detections or confirmed damage.

## 8. Expected impact

NiñoRadar aims to demonstrate how NISAR observations can improve spatial understanding of floods.

- **Scientific:** demonstrate a reproducible methodology for detecting changes in inundated surfaces using satellite radar.
- **Technological:** translate SAR data into interactive maps and exposure indicators understandable to non-specialists.
- **Social:** support preliminary identification of potentially affected areas and better prioritization of territorial verification.

These are intended outcomes, not impacts already measured.

## 9. Vision

The long-term ambition is an open, scalable tool that combines satellite observations with territorial data to support flood management across vulnerable regions.

Satellite imagery should become useful information for communities facing environmental change, extending beyond scientific laboratories and specialist platforms.

**NiñoRadar: from space to the territory, turning satellite data into information for action.**
