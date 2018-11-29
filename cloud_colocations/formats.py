"""
The :code:`formats` module provides classes to simplify the handling
of the file formats of the different data products.
"""

import numpy as np

from pyhdf.SD import SD, SDC

from cloud_colocations.products import file_cache, caliop, modis, modis_geo

################################################################################
# IcareFile
################################################################################

class IcareFile:
    """
    Base class for files from the Icare data center. Provides abstract class
    methods to obtain files for a given point in time or time range.
    """
    @classmethod
    def get_by_date(cls, t):
        """
        Return file with the latest start point earlier than the given
        datetime :code:`t`.

        Parameters:

            t(datetime.datetime): :code:`datetime` object representing the point
            in time for which to find the icare file.

        Returns:

            The file object with the latest found start time berfore the given
            time.
        """
        filename = cls.product.get_file_by_date(t)
        path     = cls.product.download_file(filename)
        return cls(path)

    @classmethod
    def get_files_in_range(cls, t0, t1):
        """
        Get files within time range.

        Parameters:

            t0(datetime.datetime): :code:`date`

        """
        filenames = cls.product.get_files_in_range(t0, t1)
        objs = []
        for f in filenames:
            path = cls.product.download_file(f)
            objs += [cls(path)]
        return objs

################################################################################
# Hdf4File
################################################################################

class Hdf4File:
    """
    Base class for file formats using HDF4File format. The :class:`Hdf4File`
    wraps around the pyhdf.SD class to implement RAII.
    """
    def __init__(self, filename):
        """
        Open an HDF4 file for reading.

        Arguments:

            filename(str): The path to the file to open.
        """
        self.filename = filename
        self.file_handle = SD(self.filename, SDC.READ)

    def __del__(self):
        self.file_handle.end()

################################################################################
# Caliop01kmclay
################################################################################

class Caliop01kmclay(Hdf4File, IcareFile):

    product = caliop

    """
    The CALIOP 1 km cloud layer data format.

    This class provide a high-level interface that wraps around the HDF
    file and provides simplified access to the data that is extracted
    for the colocations.
    """
    def __init__(self, filename):
        """
        Create :code:`Caliop01kmclay` object from file.

        Arguments:

            filename(str): Path to the file to read.

        """
        super().__init__(filename)

        self.profile_times = self.file_handle.select('Profile_Time')[:].ravel()


    def get_latitudes(self, c_i = -1, dn = 0):
        """
        Get latitudes of profile in file as :code:`numpy.ndarray`.
        """
        if c_i < 0:
            return self.file_handle.select('Latitude')[:]
        else:
            return self.file_handle.select('Latitude')[c_i - dn : c_i + dn + 1]

    def get_longitudes(self, c_i = -1, dn = 0):
        """
        Get longitudes of profile in file as :code:`numpy.ndarray`.
        """
        if c_i < 0:
            return self.file_handle.select('Longitude')[:]
        else:
            return self.file_handle.select('Longitude')[c_i - dn : c_i + dn + 1]

    def get_cloud_top_height(self, c_i = -1, dn = 0):
        """
        Get altitude of topmost layer as :code:`numpy.ndarray`. By default
        this function will return the top altitudes for the first detected
        layer for all profiles. However, if c_i and dn are give, it will
        return only the profiles in the region containing the :code:`2 * dn + 1`
        profiles centered around :code:`c_i`.

        Arguments:

            c_i(int): Profile index of colocation center.

            dn(int): Half extent of the region to extract.

        """
        if c_i < 0:
            return self.file_handle.select('Layer_Top_Altitude')[:, 0]
        else:
            return self.file_handle.select('Layer_Top_Altitude')\
                [c_i - dn : c_i + dn + 1, 0]

    def get_feature_class(self, c_i = -1, dn = 0):
        """
        Return classification flag for uppermost detected layer.

        Arguments:

            c_i(int): Profile index of colocation center.

            dn(int): Half extent of the region to extract.
        """
        if c_i < 0:
            classes = self.file_handle.select('Feature_Classification_Flags')[:, 0] % 8
        else:
            classes = self.file_handle.select('Feature_Classification_Flags')\
                [c_i - dn : c_i + dn + 1, 0] % 8
        return classes

    def get_feature_class_curtain(self, c_i = -1, dn = 0):
        if c_i < 0:
            classes = self.file_handle.select('Feature_Classification_Flags')[:, :] % 8
        else:
            classes = self.file_handle.select('Feature_Classification_Flags')\
                [c_i - dn : c_i + dn + 1, :] % 8
        return classes

    def get_cloud_class(self, c_i = -1, dn = 0):
        """
        Return classification flag for uppermost detected layer.

        Arguments:

            c_i(int): Profile index of colocation center.

            dn(int): Half extent of the region to extract.
        """
        if c_i < 0:
            classes = self.file_handle.select('Feature_Classification_Flags')[:, 0]
        else:
            classes = self.file_handle.select('Feature_Classification_Flags') \
                [c_i - dn : c_i + dn + 1, 0]

        cloud_types = np.zeros(classes.shape)
        inds = (classes % 8) == 2
        cloud_types[inds] = (classes[inds] // 1024) % 8
        return cloud_types

    def get_feature_class_quality(self, c_i = -1, dn = 0):
        """
        Return classification flag for uppermost detected layer.

        Arguments:

            c_i(int): Profile index of colocation center.

            dn(int): Half extent of the region to extract.
        """
        if c_i < 0:
            classes = self.file_handle.select('Feature_Classification_Flags')[:, 0]
        else:
            classes = self.file_handle.select('Feature_Classification_Flags') \
                [c_i - dn : c_i + dn + 1, 0]
        return (classes // 8) % 4

    def get_cloud_top_pressure(self, c_i = -1, dn = 0):
        """
        Get pressure of topmost layer as :code:`numpy.ndarray`. By default
        this function will return the top pressure for the first detected
        layer for all profiles. However, if c_i and dn are give, it will
        return only the profiles in the region containing the :code:`2 * dn + 1`
        profiles centered around :code:`c_i`.

        Arguments:

            c_i(int): Profile index of colocation center.

            dn(int): Half extent of the region to extract.

        """
        if c_i < 0:
            return self.file_handle.select('Layer_Top_Pressure')[:, 0]
        else:
            return self.file_handle.select('Layer_Top_Pressure')[c_i - dn : c_i + dn + 1, 0]


    def get_utc_time(self, c_i = -1, dn = 0):
        """
        Returns the UTC times for all profiles in the file as numpy array.
        """
        if c_i < 0:
            return self.file_handle.select('Profile_UTC_Time')[:]
        else:
            return self.file_handle.select('Profile_UTC_Time')[c_i - dn : c_i + dn + 1]


    def get_profile_times(self, c_i = -1, dn = 0):
        """
        Returns the profile times for all profiles in the file as numpy array.
        """
        if c_i < 0 or dn < 0:
            return self.file_handle.select('Profile_Time')[:]
        else:
            return self.file_handle.select('Profile_Time')[c_i - dn : c_i + dn + 1]

    def get_profile_id(self, c_i, dn):
        return self.file_handle.select('Profile_ID')[c_i - dn : c_i + dn + 1]


################################################################################
# Caliop01kmclay
################################################################################

class ModisMyd03(Hdf4File, IcareFile):
    """
    The MODIS Aqua geolocation file format containing geolocation data
    corresponding to the L1B radiances.
    """

    product = modis_geo

    def __init__(self, filename):
        super().__init__(filename)

        self.lats = self.file_handle.select('Latitude')[:, :]
        self.lons = self.file_handle.select('Longitude')[:, :]

        self.i_cached = None
        self.j_cached = None
        self.cache_range = 10

    def get_latitudes(self):
        return self.lats

    def get_longitudes(self):
        return self.lons

    def _get_colocation(self, lat, lon, lats, lons):
        from geopy.distance import distance

        m, n = lats.shape

        dlats = lats - lat
        dlons = lons - lon

        d = (dlats) ** 2 + (dlons) ** 2
        ind = np.argmin(d.ravel())

        i = ind // n
        j = ind % n

        return i, j, distance((lat, lon), (lats[i, j], lons[i, j])).km

    def get_colocation(self, lat, lon, d_max = 1.0, use_cache = True):

        if use_cache and self.i_cached and self.j_cached:
            i_start = max(self.i_cached - self.cache_range, 0)
            i_end   = self.i_cached + self.cache_range
            j_start = max(self.j_cached - self.cache_range, 0)
            j_end   = self.j_cached + self.cache_range
            i, j, d = self._get_colocation(lat, lon,
                                            self.lats[i_start : i_end, j_start : j_end],
                                            self.lons[i_start : i_end, j_start : j_end])
            if d < d_max:
                return i, j, d

        i, j, d = self._get_colocation(lat, lon, self.lats, self.lons)

        if d < d_max:
            self.i_cached = i
            self.j_cached = j

        return i, j, d


class ModisMyd021km(Hdf4File, IcareFile):
    """
    The MODIS Aqua Level1B calibrated radiances at 1 km resolution.
    """

    product = modis

    def __init__(self, filename):
        super().__init__(filename)
        self._data = None

    def load_data(self):

        raw_data = self.file_handle.select("EV_250_Aggr1km_RefSB")
        shape = raw_data.info()[2]

        # Channels 1 - 2 
        self._data = np.zeros((38, shape[1], shape[2]))
        self.m = shape[1]
        self.n = shape[2]
        self._data[:2, :, :] = raw_data[:, :, :]
        data = self._data[:2, :, :]

        attributes = raw_data.attributes()
        valid_range = attributes["valid_range"]
        valid_min = valid_range[0]
        valid_max = valid_range[1]
        offsets     = np.asarray(attributes["reflectance_offsets"])
        scales      = np.asarray(attributes["reflectance_scales"])
        fill_value  = attributes["_FillValue"]

        invalid = np.logical_or(data > valid_max,
                                data < valid_min)
        invalid = np.logical_or(invalid, data == fill_value)
        data[invalid] = np.nan

        for i in range(2):
            data[i, :, :] = (data[i, :, :] - offsets[i]) * scales[i]

        # Channels 3 - 8 
        raw_data = self.file_handle.select("EV_500_Aggr1km_RefSB")
        self._data[2:7, :, :] = raw_data[:, :, :]
        data = self._data[2:7, :, :]

        attributes = raw_data.attributes()
        valid_range = attributes["valid_range"]
        valid_min = valid_range[0]
        valid_max = valid_range[1]
        offsets     = np.asarray(attributes["reflectance_offsets"])
        scales      = np.asarray(attributes["reflectance_scales"])
        fill_value  = attributes["_FillValue"]

        invalid = np.logical_or(data > valid_max,
                                data < valid_min)
        invalid = np.logical_or(invalid, data == fill_value)
        data[invalid] = np.nan

        for i in range(5):
            data[i, :, :] = (data[i, :, :] - offsets[i]) * scales[i]

        # Channels 8 - 22 
        raw_data = self.file_handle.select("EV_1KM_RefSB")
        self._data[7:21, :, :] = raw_data[:14, :, :]
        data = self._data[7:21, :, :]

        attributes = raw_data.attributes()
        valid_range = attributes["valid_range"]
        valid_min = valid_range[0]
        valid_max = valid_range[1]
        offsets     = np.asarray(attributes["reflectance_offsets"])
        scales      = np.asarray(attributes["reflectance_scales"])
        fill_value  = attributes["_FillValue"]

        invalid = np.logical_or(data > valid_max,
                                data < valid_min)
        invalid = np.logical_or(invalid, data == fill_value)
        data[invalid] = np.nan

        for i in range(14):
            data[i, :, :] = (data[i, :, :] - offsets[i]) * scales[i]

        # Channels 20 - 26 
        raw_data = self.file_handle.select("EV_1KM_Emissive")
        self._data[21:27, :, :] = raw_data[:6, :, :]
        data = self._data[21:27, :, :]

        attributes = raw_data.attributes()
        valid_range = attributes["valid_range"]
        valid_min = valid_range[0]
        valid_max = valid_range[1]
        offsets     = np.asarray(attributes["radiance_offsets"])
        scales      = np.asarray(attributes["radiance_scales"])
        fill_value  = attributes["_FillValue"]

        invalid = np.logical_or(data > valid_max,
                                data < valid_min)
        invalid = np.logical_or(invalid, data == fill_value)
        data[invalid] = np.nan

        for i in range(6):
            data[i, :, :] = (data[i, :, :] - offsets[i]) * scales[i]

        # Channel 26
        raw_data = self.file_handle.select("EV_Band26")
        self._data[27, :, :] = raw_data[:, :]
        data = self._data[27, :, :]

        attributes = raw_data.attributes()
        valid_range = attributes["valid_range"]
        valid_min = valid_range[0]
        valid_max = valid_range[1]
        offsets     = np.asarray(attributes["radiance_offsets"])
        scales      = np.asarray(attributes["radiance_scales"])
        fill_value  = attributes["_FillValue"]

        invalid = np.logical_or(data > valid_max,
                                data < valid_min)
        invalid = np.logical_or(invalid, data == fill_value)
        data[invalid] = np.nan

        data[:, :] = (data[:, :] - offsets) * scales

        # Channels 28 - 38 
        raw_data = self.file_handle.select("EV_1KM_Emissive")
        self._data[28:38, :, :] = raw_data[6:, :, :]
        data = self._data[28:38, :, :]

        attributes = raw_data.attributes()
        valid_range = attributes["valid_range"]
        valid_min = valid_range[0]
        valid_max = valid_range[1]
        offsets     = np.asarray(attributes["radiance_offsets"])
        scales      = np.asarray(attributes["radiance_scales"])
        fill_value  = attributes["_FillValue"]

        invalid = np.logical_or(data > valid_max,
                                data < valid_min)
        invalid = np.logical_or(invalid, data == fill_value)
        data[invalid] = np.nan

        for i in range(9):
            data[i, :, :] = (data[i, :, :] - offsets[6 + i]) * scales[6 + i]

    @property
    def data(self):
        if self._data is None:
            self.load_data()
        return self._data

    def get_input_data(self, c_i, c_j, dn):
        bands = [20, 27, 28, 29, 31, 32, 33]
        band_offsets = [20, 21, 21, 21, 21, 21, 21]
        ds_name = "EV_1KM_Emissive"

        raw_data = self.file_handle.select(ds_name)
        data = raw_data

        res = np.zeros((len(bands), 2 * dn + 1, 2 * dn + 1))

        attributes = raw_data.attributes()
        valid_range = attributes["valid_range"]
        offsets = attributes["radiance_offsets"]
        scales  = attributes["radiance_scales"]
        fill_value = attributes["_FillValue"]

        for i, (b, o) in enumerate(zip(bands, band_offsets)):
            valid_min = valid_range[0]
            valid_max = valid_range[1]
            offset = offsets[b - o]
            scale_factor = scales[b - o]

            res[i, :, :] = data[int(b - o),
                                int(c_i - dn) : int(c_i + dn + 1),
                                int(c_j - dn) : int(c_j + dn + 1)]
            invalid = np.logical_or(res[i, :, :] > valid_max,
                                    res[i, :, :] < valid_min)
            invalid = np.logical_or(invalid, res[i, :, :] == fill_value)
            res[i, invalid] = np.nan

            res[i, :, :] = (res[i, :, :] - offset) * scale_factor
        return res