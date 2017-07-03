## ESPA Processing Version 2.20.1 Release Notes

Release Date: July 2017

See git tag [espa-2.20.1-release]

### General Information
This project contains the code for processing a single input dataset to the final output products.  It is the controlling code for producing a product.  It does not produce science products on it's own, it calls on applications from other ESPA projects to perform that work.  Having said that, it does contain some code to perform a few things, such as, statistics generation, statistics plotting, and warping (using GDAL).

## Release Notes
Please see the Release Tags for notes related to past versions.

- Version change for system wide versioning
- Bug fix to add the pixel_size parameters when they are required.

## Supported Science Products
To generate products for a science application, it must be installed on the system and the applications provided must be available on the PATH.  See the respective science projects for installation instructions and auxiliary data requirements.

For the core capabilities required by each science application including this project.  See  [espa-product-formatter](https://github.com/USGS-EROS/espa-product-formatter).

- CFmask - See [espa-cloud-masking](https://github.com/USGS-EROS/espa-cloud-masking)
- Elevation - See [espa-elevation](https://github.com/USGS-EROS/espa-elevation)
- Land Surface Temperature - See [espa-land-surface-temperature](https://github.com/USGS-EROS/espa-land-surface-temperature)
- Top of Atmosphere and Surface Reflectance - See [espa-surface-reflectance](https://github.com/USGS-EROS/espa-surface-reflectance)
- Spectral Indices - See [espa-spectral-indices](https://github.com/USGS-EROS/espa-spectral-indices)
- Surface Water Extent - See [espa-surface-water-extent](https://github.com/USGS-EROS/espa-surface-water-extent)
- L2 QA Tools - See [espa-l2qa-tools](https://github.com/USGS-EROS/espa-l2qa-tools)

## Installation Notes
TODO - Need to fill in this section.

## Usage
TODO - Need to fill in this section.

## More Information
This project is provided by the US Geological Survey (USGS) Earth Resources
Observation and Science (EROS) Land Satellite Data Systems (LSDS) Science
Research and Development (LSRD) Project. For questions regarding products
produced by this source code, please contact the Landsat Contact Us page and
specify USGS CDR/ECV in the "Regarding" section.
https://landsat.usgs.gov/contactus.php
