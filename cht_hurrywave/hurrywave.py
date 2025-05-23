# -*- coding: utf-8 -*-
"""
Created on Sat May 15 08:08:40 2021

@author: ormondt
"""
import os
import pandas as pd
import datetime
import numpy as np
import xarray as xr

import math
from pyproj import CRS
from pyproj import Transformer

from .input import HurryWaveInput
# Bathymetry and mask are now part of HurryWaveGrid class
from .grid import HurryWaveGrid
from .waveblocking import WaveBlocking
from .boundary_conditions import HurryWaveBoundaryConditions
from .observation_points import HurryWaveObservationPointsRegular
from .observation_points import HurryWaveObservationPointsSpectra

class HurryWave:

    """
    A class representing the HurryWave model, used for simulating wave dynamics, 
    boundary conditions, and observation points.

    The class provides functionality to:
    - Initialize and configure model inputs, grid, boundary conditions, and observation points.
    - Read and write model data and input files.
    - Manage spatial data, including grid coordinates, boundaries, and bathymetry.
    - Read and process time-series and map outputs from the model.
    - Generate tiling indices for specific zoom levels.

    Key Methods:
    
    - __init__: 
        Initializes the HurryWave model with optional configuration settings for path, CRS, and exe path.
    - read_input_file: 
        Reads the input file and sets up the model's configuration.
    - clear_spatial_attributes: 
        Clears spatial data related to grid, boundary conditions, and observation points.
    - write:
         Writes input data and attribute files to disk.
    - read_timeseries_output: 
        Reads model output for time-series data, such as wave height or direction.
    - read_map_output_max: 
        Reads and processes maximum values from model map outputs.
    - grid_coordinates: 
        Computes grid coordinates for the model, either in grid or corrected format.
    - bounding_box: 
        Returns the spatial extent (bounding box) of the model grid.
    - outline:
         Returns the outline of the model domain.
    - make_index_tiles:
         Generates and writes index tiles for the model grid at specified zoom levels.
    """
    
    def __init__(self, load=False, crs=None, path=None, exe_path=None, read_grid_data=True):
        # HurryWave can be initialized in THREE ways
        # hw = HurryWave() -> path is set to CWD
        # hw = HurryWave(path="d:\\temp") -> path is set to path
        # hw = HurryWave(path="d:\\temp", load=True) -> path is set to path, and input file is read

        if not crs:
            self.crs = CRS(4326)
        else:
            self.crs = crs

        if not path:
            self.path = os.getcwd()
        else:
            self.path = path

        if not exe_path:
            self.exe_path = None
        else:
            self.exe_path = exe_path

        # Initialize input variables
        self.input                      = HurryWaveInput(self)

        if load:
            self.input.read()
            # Get CRS from input file
            self.crs = CRS(self.input.variables.crs_name)

        self.grid                       = HurryWaveGrid(self)
        self.boundary_conditions        = HurryWaveBoundaryConditions(self)
        self.observation_points_regular = HurryWaveObservationPointsRegular(self)
        self.observation_points_sp2     = HurryWaveObservationPointsSpectra(self)
        self.waveblocking               = WaveBlocking(self)
        self.obstacle                   = []

        # Now read the attribute files
        if load:
            self.read_attribute_files(read_grid_data=read_grid_data)

    def clear_spatial_attributes(self):
        # Clear all spatial data
        self.grid                       = HurryWaveGrid(self)
        self.boundary_conditions        = HurryWaveBoundaryConditions(self)
        self.observation_points_regular = HurryWaveObservationPointsRegular(self)
        self.observation_points_sp2     = HurryWaveObservationPointsSpectra(self)

    def read(self, path=None, read_grid_data=True):
        if path:
            self.path = path
        self.input.read()
        # Get CRS from input file
        self.crs = CRS(self.input.variables.crs_name)
        self.read_attribute_files(read_grid_data=read_grid_data)

    def read_input_file(self):
        self.input.read()
        # Get CRS from input file
        self.crs = CRS(self.input.variables.crs_name)

    def read_attribute_files(self, read_grid_data=True):
        if read_grid_data:
            self.grid.read()
        self.boundary_conditions.read()
        self.observation_points_regular.read()
        self.observation_points_sp2.read()

    def write(self):
        self.input.write()
        self.write_attribute_files()
        
    def write_attribute_files(self):
        self.grid.write()
        self.boundary_conditions.write()
        self.observation_points_regular.write()
        self.observation_points_sp2.write()

    def write_batch_file(self):
        fid = open(os.path.join(self.path, "run.bat"), "w")
        fid.write(self.exe_path + "\\" + "hurrywave.exe")
        fid.close()

    def set_path(self, path):
        self.path = path
        
    def list_observation_points_regular(self):
        return self.observation_points_regular.list_observation_points()

    def list_observation_points_spectra(self):
        return self.observation_points_spectra.list_observation_points()

    ### Output ###
    def read_timeseries_output(self,
                               name_list = None,
                               path=None,
                               file_name = None,
                               parameter = "hm0"):

        import xarray as xr
        import pandas as pd
        import numpy as np

        # Returns a dataframe with timeseries    
        # parameter options: hm0, tp, wavdir, dirsp        
        if not path:
            path = self.path

        if not file_name:
            file_name = "hurrywave_his.nc"

        file_name = os.path.join(path, file_name)
                    
        # Open netcdf file
        ddd = xr.open_dataset(file_name)
        stations=ddd.station_name.values
        all_stations = []
        for ist, st in enumerate(stations):
            st=str(st.strip())[2:-1]
            all_stations.append(st)
        
        times   = ddd.point_hm0.coords["time"].values

        # If name_list is empty, add all points    
        if not name_list:
            name_list = []
            for st in all_stations:
                name_list.append(st)
        
        df = pd.DataFrame(index=times, columns=name_list)
        
        data_tmp = ddd["point_" + parameter]

        for station in name_list:
            for ist, st in enumerate(all_stations):
                if station == st:
                    data = data_tmp.isel(stations=ist).values
                    data[np.isnan(data)] = -999.0
                    df[st]=data
                    break            

        ddd.close()
        
        return df    
        
        # # Returns a dataframe with timeseries
    
        # if not file_name:
        #     file_name = os.path.join(self.path, "zst.txt")
    
        # if not self.observation_point:
        #     # First read observation points
        #     self.read_observation_points()
        
        # columns = []
        # for point in self.observation_point:
        #     columns.append(point.name)
            
        # df = read_timeseries_file(file_name, self.input.tref)

        # # Add column names
        # df.columns = columns
            
        # if name_list:
        #     df = df[name_list]
            
        # return df    
    def read_map_output_max(self, time_range=None, map_file=None, parameter = "hm0"):
    
        if not map_file:
            map_file = os.path.join(self.path, "hurrywave_map.nc")
            
        dsin = xr.open_dataset(map_file)

        output_times = dsin.timemax.values
        if time_range is None:

            t0 = pd.to_datetime(str(output_times[0])).replace(tzinfo=None).to_pydatetime()
            t1 = pd.to_datetime(str(output_times[-1])).replace(tzinfo=None).to_pydatetime()
            time_range = [t0, t1]

        it0 = -1
        for it, time in enumerate(output_times):
            time = pd.to_datetime(str(time)).replace(tzinfo=None).to_pydatetime()
            if time>=time_range[0] and it0<0:
                it0 = it
            if time<=time_range[1]:
                it1 = it
        
        zs_da = np.amax(dsin[parameter].values[it0:it1,:,:], axis=0)
        dsin.close()
        
        return zs_da


    def read_hm0max(self, time_range=None, hm0max_file=None, parameter='hm0max'):
    
        if not hm0max_file:
            hm0max_file = os.path.join(self.path, "hm0max.dat")
            
        fname, ext = os.path.splitext(hm0max_file)
        
        if ext == ".dat":

            ind_file = os.path.join(self.path, self.input.variables.indexfile)
    
            freqstr = str(self.input.variables.dtmaxout) + "S"
            t00     = datetime.timedelta(seconds=self.input.variables.t0out + self.input.variables.dtmaxout)
            output_times = pd.date_range(start=self.input.variables.tstart + t00,
                                          end=self.input.variables.tstop,
                                          freq=freqstr).to_pydatetime().tolist()
            nt = len(output_times)
            
            if time_range is None:
                time_range = [self.input.variables.tstart + t00, self.input.variables.tstop]
            
            for it, time in enumerate(output_times):
                if time<=time_range[0]:
                    it0 = it
                if time<=time_range[1]:
                    it1 = it
    
            # Get maximum values
            nmax = self.input.variables.nmax + 2
            mmax = self.input.variables.mmax + 2
                            
            # Read sfincs.ind
            data_ind = np.fromfile(ind_file, dtype="i4")
            npoints = data_ind[0]
            data_ind = np.squeeze(data_ind[1:])
            
            # Read zsmax file
            data_zs = np.fromfile(hm0max_file, dtype="f4")
            data_zs = np.reshape(data_zs,[nt, npoints + 2])[it0:it1+1, 1:-1]

            data_zs = np.amax(data_zs, axis=0)
            zs_da = np.full([nmax*mmax], np.nan)        
            zs_da[data_ind - 1] = np.squeeze(data_zs)
            zs_da = np.where(zs_da == -999, np.nan, zs_da)
            zs_da = np.transpose(np.reshape(zs_da, [mmax, nmax]))[1:-1,1:-1]
        
        elif ext==".nc":

            dsin = xr.open_dataset(hm0max_file)

            output_times = dsin.timemax.values
            if time_range is None:

                t0 = pd.to_datetime(str(output_times[0])).replace(tzinfo=None).to_pydatetime()
                t1 = pd.to_datetime(str(output_times[-1])).replace(tzinfo=None).to_pydatetime()
                time_range = [t0, t1]

            it0 = -1
            for it, time in enumerate(output_times):
                time = pd.to_datetime(str(time)).replace(tzinfo=None).to_pydatetime()
                if time>=time_range[0] and it0<0:
                    it0 = it
                if time<=time_range[1]:
                    it1 = it            
            
            zs_da = np.amax(dsin[parameter].values[it0:it1,:,:], axis=0)
            dsin.close()
            
        else:
            # Must be txt file
            return None
        

        return zs_da
        
#     def write_hmax_geotiff(self, dem_file, index_file, hmax_file, time_range=None, zsmax_file=None):
        
#         no_datavalue = -9999
    
#         zs_da = self.read_zsmax(time_range=time_range, zsmax_file=zsmax_file)
#         zs_da = 100 * zs_da
        
#         # Read indices for DEM and resample SFINCS max. water levels on DEM grid
#         dem_ind   = np.fromfile(index_file, dtype="i4")
#         ndem      = dem_ind[0]
#         mdem      = dem_ind[1]
#         indices   = dem_ind[2:]
#         zsmax_dem = np.zeros_like(indices)
#         zsmax_dem = np.where(zsmax_dem == 0, np.nan, 0)
#         valid_indices = np.where(indices > 0)
#         indices = np.where(indices == 0, 1, indices)
#         indices = indices - 1  # correct for python start counting at 0 (matlab at 1)
#         zsmax_dem[valid_indices] = zs_da[indices][valid_indices]
#         zsmax_dem = np.flipud(zsmax_dem.reshape(mdem, ndem).transpose())

#         # Open DEM file
#         dem_ds = gdal.Open(dem_file)
#         band = dem_ds.GetRasterBand(1)
#         dem = band.ReadAsArray()
#         # calculate max. flood depth as difference between water level zs and dem, do not allow for negative values
#         hmax_dem = zsmax_dem - dem  ## just for testing
#         hmax_dem = np.where(hmax_dem < 0, 0, hmax_dem)
#         # set no data value to -9999
#         hmax_dem = np.where(np.isnan(hmax_dem), no_datavalue, hmax_dem)
#         # convert cm to m
#         hmax_dem = hmax_dem/100

#         # write max. flood depth (in m) to geotiff
#         [cols, rows] = dem.shape
#         driver = gdal.GetDriverByName("GTiff")
#         outdata = driver.Create(hmax_file, rows, cols, 1, gdal.GDT_Float32)
#         outdata.SetGeoTransform(dem_ds.GetGeoTransform())  ## sets same geotransform as input
#         outdata.SetProjection(dem_ds.GetProjection())      ## sets same projection as input
#         outdata.GetRasterBand(1).WriteArray(hmax_dem)
#         outdata.GetRasterBand(1).SetNoDataValue(no_datavalue)  ## if you want these values transparent
# #        outdata.SetMetadata({k: str(v) for k, v in scenarioDict.items()})

#         outdata.FlushCache()  ## saves to disk!!
#         outdata = None
#         band = None
#         dem_ds = None

    def grid_coordinates(self, loc='cor'):

        cosrot = math.cos(self.input.variables.rotation*math.pi/180)
        sinrot = math.sin(self.input.variables.rotation*math.pi/180)
        if loc=="cor":
            xx     = np.linspace(0.0,
                                 self.input.variables.mmax*self.input.variables.dx,
                                 num=self.input.variables.mmax + 1)
            yy     = np.linspace(0.0,
                                 self.input.variables.nmax*self.input.variables.dy,
                                 num=self.input.variables.nmax + 1)
        else:
            xx     = np.linspace(0.5*self.input.variables.dx,
                                 self.input.variables.mmax*self.input.variables.dx - 0.5*self.input.variables.dx,
                                 num=self.input.variables.mmax)
            yy     = np.linspace(0.5*self.input.variables.dy,
                                 self.input.variables.nmax*self.input.variables.dy - 0.5*self.input.variables.dy,
                                 num=self.input.variables.nmax)
            
        xg0, yg0 = np.meshgrid(xx, yy)
        xg = self.input.variables.x0 + xg0*cosrot - yg0*sinrot
        yg = self.input.variables.y0 + xg0*sinrot + yg0*cosrot

        return xg, yg
    
    def bounding_box(self, crs=None):

        xg, yg = self.grid_coordinates(loc='cor')
        
        if crs:
            transformer = Transformer.from_crs(self.crs,
                                               crs,
                                               always_xy=True)
            xg, yg = transformer.transform(xg, yg)
        
        x_range = [np.min(np.min(xg)), np.max(np.max(xg))]
        y_range = [np.min(np.min(yg)), np.max(np.max(yg))]
        
        return x_range, y_range

    def outline(self, crs=None):

        xg, yg = self.grid_coordinates(loc='cor')
        
        if crs:
            transformer = Transformer.from_crs(self.crs,
                                               crs,
                                               always_xy=True)
            xg, yg = transformer.transform(xg, yg)
        
        xp = [ xg[0,0], xg[0,-1], xg[-1,-1], xg[-1,0], xg[0,0] ]
        yp = [ yg[0,0], yg[0,-1], yg[-1,-1], yg[-1,0], yg[0,0] ]
        
        return xp, yp
        
    def make_index_tiles(self, path, zoom_range=None,  
                         z_range=None,
                         dem_names=None):
        
        from cht_tiling.tiling import deg2num
        from cht_tiling.tiling import num2deg
        import cht_utils.fileops as fo
        
        if not zoom_range:
            zoom_range = [0, 13]

        npix = 256
        
        # Compute lon/lat range
        lon_range, lat_range = self.bounding_box(crs=CRS.from_epsg(4326))
        
        cosrot = math.cos(-self.input.variables.rotation*math.pi/180)
        sinrot = math.sin(-self.input.variables.rotation*math.pi/180)       
        
        transformer_a = Transformer.from_crs(CRS.from_epsg(4326),
                                             CRS.from_epsg(3857),
                                             always_xy=True)
        transformer_b = Transformer.from_crs(CRS.from_epsg(3857),
                                             self.crs,
                                             always_xy=True)

        # Remove existing path
        if os.path.exists(path):
            print("Removing existing path " + path)
            fo.rmdir(path)
            
        if z_range:
            # Only want data in specific range
            # Need to do some other stuff here
            from cht_bathymetry.bathymetry_database import bathymetry_database
            from cht_tiling.tiling import get_bathy_on_tile

            for dem_name in dem_names:
                dem_crs = []
                transformer_3857_to_dem = []                
                for dem_name in dem_names:                
                    dem_crs.append(bathymetry_database.get_crs(dem_name))            
                    transformer_3857_to_dem.append(Transformer.from_crs(CRS.from_epsg(3857),
                                                                        dem_crs[-1],
                                                                        always_xy=True))
        
        for izoom in range(zoom_range[0], zoom_range[1] + 1):
            
            print("Processing zoom level " + str(izoom))
        
            zoom_path = os.path.join(path, str(izoom))
        
            dxy = (40075016.686/npix) / 2 ** izoom
            xx = np.linspace(0.0, (npix - 1)*dxy, num=npix)
            yy = xx[:]
            xv, yv = np.meshgrid(xx, yy)
        
            ix0, iy0 = deg2num(lat_range[0], lon_range[0], izoom)
            ix1, iy1 = deg2num(lat_range[1], lon_range[1], izoom)
        
            for i in range(ix0, ix1 + 1):
            
                path_okay = False
                zoom_path_i = os.path.join(zoom_path, str(i))
            
                for j in range(iy0, iy1 + 1):
            
                    file_name = os.path.join(zoom_path_i, str(j) + ".dat")
            
                    # Compute lat/lon at lower-left corner of tile
                    lat, lon = num2deg(i, j, izoom)
            
                    # Convert to Global Mercator
                    xo, yo   = transformer_a.transform(lon,lat)
            
                    # Tile grid on Global Mercator
                    xm = xv[:] + xo + 0.5*dxy
                    ym = yv[:] + yo + 0.5*dxy
                                
                    # Convert tile grid to crs of HurryWave model
                    x,y      = transformer_b.transform(xm, ym)
                    
                    # Now rotate around origin of HurryWave model
                    x00 = x - self.input.variables.x0
                    y00 = y - self.input.variables.y0
                    xg  = x00*cosrot - y00*sinrot
                    yg  = x00*sinrot + y00*cosrot
                    
                    iind = np.floor(xg/self.input.variables.dx).astype(int)
                    jind = np.floor(yg/self.input.variables.dy).astype(int)
                    ind  = iind*self.input.variables.nmax + jind
                                        
                    ind[iind<0]   = -999
                    ind[jind<0]   = -999
                    ind[iind>=self.input.variables.mmax] = -999
                    ind[jind>=self.input.variables.nmax] = -999

                    if z_range:
                        # Need temporarily create topo indices here to make indices
                        # only for specific depth ranges
                        z = get_bathy_on_tile(xm, ym,
                                              dem_names,
                                              dem_crs,
                                              transformer_3857_to_dem,
                                              dxy,
                                              bathymetry_database)
                        ind[z<z_range[0]] = -999
                        ind[z>z_range[1]] = -999

                    # if self.mask:
                    if ind.max()>=0:
                        # Do not include points with mask<1
                        ingrid      = np.where(ind>=0)
                        msk         = np.zeros((256,256), dtype=int) + 1
                        msk[ingrid] = self.grid.ds["mask"].values[jind[ingrid], iind[ingrid]]
                        iex         = np.where(msk<1)
                        ind[iex]    = -999
                    
                    if np.any(ind>=0):                     
                        if not path_okay:
                            if not os.path.exists(zoom_path_i):
                                fo.mkdir(zoom_path_i)
                                path_okay = True                             
                        # And write indices to file
                        fid = open(file_name, "wb")
                        fid.write(ind)
                        fid.close()


    def setup_wind_uniform_forcing(self, timeseries=None, magnitude=None, direction=None):
        """Setup spatially uniform wind forcing (wind).

        Adds model layers:

        * **windfile** forcing: uniform wind magnitude [m/s] and direction [deg]

        Parameters
        ----------
        timeseries, str, Path
            Path to tabulated timeseries csv file with time index in first column,
            magnitude in second column and direction in third column
            see :py:meth:`hydromt.open_timeseries_from_table`, for details.
            Note: tabulated timeseries files cannot yet be set through the data_catalog yml file.
        magnitude: float
            Magnitude of the wind [m/s]
        direction: float
            Direction where the wind is coming from [deg], e.g. 0 is north, 90 is east, etc.
        """
        tstart, tstop = self.input.variables.tstart, self.input.variables.tstop
        if timeseries is not None:
            if timeseries is isinstance(str):
                df_ts = pd.read_csv(timeseries, index = [0], header = None)
            else:
                 raise ValueError(
                "Timeseries should be path to csv file"
            )


        elif magnitude is not None and direction is not None:
            df_ts = pd.DataFrame(
                index=pd.date_range(tstart, tstop, periods=2),
                data=np.array([[magnitude, direction], [magnitude, direction]]),
                columns=["mag", "dir"],
            )
        else:
            raise ValueError(
                "Either timeseries or magnitude and direction must be provided"
            )

        df_ts.name = "wnd"
        df_ts.index.name = "time"
        df_ts.columns.name = "index"

        df_ts.index =  df_ts.index - self.input.variables.tref
        df_ts.index = df_ts.index.total_seconds()

        df_ts.to_csv(os.path.join(self.path, "hurrywave.wnd"), sep=" ", header=False)


# class HurryWaveGrid():
#
#     def __init__(self, x0, y0, dx, dy, nx, ny, rotation):
#         self.geometry = RegularGrid(x0, y0, dx, dy, nx, ny, rotation)

    # def plot(self,ax):
    #     self.geometry.plot(ax)

    # def corner_coordinates(self):
    #     x,y = self.geometry.grid_coordinates_corners()
    #     return x, y

    # def centre_coordinates(self):
    #     x,y = self.geometry.grid_coordinates_centres()
    #     return x, y

# class HurryWaveDepth():
#     def __init__(self):
#         self.value = []
#         self.geometry = []
#     def plot(self,ax):
#         pass
#     def read(self):
#         pass

# class HurryWaveMask():
#     def __init__(self):
#         self.msk = []
#     def plot(self,ax):
#         pass

# class HurryWaveBoundaryConditions():
#
#     def __init__(self):
#         self.geometry = []
#
#     def read(self, bndfile, bzsfile):
#         self.read_points(bndfile)
#         self.read_time_series(bzsfile)
#
#     def read_points(self, file_name):
#         pass
#
#     def read_time_series(self, file_name):
#         pass
#
#     def set_xy(self, x, y):
#         self.geometry.x = x
#         self.geometry.y = y
#         pass
#
#     def plot(self,ax):
#         pass

# class HurryWaveBoundaryConditions():
#
#     def __init__(self):
#         self.geometry = []
#
#     def read(self, bndfile, bzsfile):
#         self.read_points(bndfile)
#         self.read_time_series(bzsfile)
#
#     def read_points(self, file_name):
#         pass
#
#     def read_time_series(self, file_name):
#         pass
#
#     def set_xy(self, x, y):
#         self.geometry.x = x
#         self.geometry.y = y
#         pass
#
#     def plot(self,ax):
#         pass


                    
def read_timeseries_file(file_name, ref_date):
    
    # Returns a dataframe with time series for each of the columns

    df = pd.read_csv(file_name, index_col=0, header=None,
                      delim_whitespace=True)
    ts = ref_date + pd.to_timedelta(df.index, unit="s")
    df.index = ts
    
    return df
    