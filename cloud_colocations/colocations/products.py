"""
The :code:`products` module provides interfaces for different data
products to lookup and download data specific files.

Atributes:

    caliop(IcareProduct): The CALIOP 01kmCLay data product.
    modis(IcareProduct): The MODIS MYD021 data product.
    modis(IcareProduct): The MODIS MYD03 geolocation product.

"""
from ftplib   import FTP
from datetime import datetime, timedelta
from cloud_colocations import settings
from xml.etree import ElementTree
import os, re, requests, shutil, tempfile
import numpy as np
import time

def ensure_extension(path, ext):
    if not any([path[-len(e):] == e for e in ext]):
        path = path + ext[0]
    return path

################################################################################
# File cache
################################################################################

class FileCache:
    """
    Simple file cache to avoid downloading files multiple times.

    Attributes:

        path(str): Path of folder containing the cache
    """
    def __init__(self, path = None):
        """
        Create a file cache.

        Arguments:

            path(str): Folder to use as file path. If not provided a
                temporary directory is created.
        """
        if path is None:
            self.path = tempfile.mkdtemp()
            self.temp = True
        else:
            self.path = path
            self.temp = False

    def get(self, filename):
        """
        Lookup file from cache.

        Arguments:

            filename(str): Filename to lookup.

        Returns:

            The full path of the file in the cache or None if
            the file is not found.

        """
        path = os.path.join(self.path, filename)
        if os.path.isfile(path):
            return path
        else:
            None

    def set_path(self, path):
        self.path = path

        if self.temp:
            shutil.rmtree(self.path)
        self.temp = False

    def __del__(self):
        if not shutil is None:
            if self.temp:
                shutil.rmtree(self.path)

file_cache = FileCache()

def set_cache(path):
    """
    Use a local cache.

    Arguments:

        path(:code:`str`): Path to the local cache.

    """
    globals()["file_cache"] = FileCache(path = path)

def get_cache_path():
    return globals()["file_cache"].path

################################################################################
# Base class for data products
################################################################################

from abc import ABCMeta, abstractmethod

class DataProduct(metaclass = ABCMeta):
    """
    The DataProduct class implements generic methods related to querying
    satellite product files.
    """
    def __init__(self):
        pass

    @abstractmethod
    def get_files(self, year, day):
        """
        This method should return a list of strings containing all files available
        for a given day.

        Arguments:

            year(int): 4-digit number representing the year from which to retrieve
                the data.

            day(int): The Julian day of the year from which to retrieve the data.
        """
        pass

    @abstractmethod
    def name_to_date(self, filename):
        """
        This method should return a :class:`datetime` object corresponding to
        the start time of this data file.
        """
        pass

    def get_preceeding_file(self, filename):
        """
        Return filename of the file that preceeds the given filename in time.

        Arguments:

            filename(str): The name of the file of which to find the preceeding one.

        Returns:

            The filename of the file preceeding the file with the given filename.

        """
        t = self.name_to_date(filename)

        year = t.year
        day  = int((t.strftime("%j")))
        files = self.get_files(year, day)

        i = files.index(filename)

        if i == 0:
            dt = timedelta(days = 1)
            t_p = t - dt
            year = t_p.year
            day  = int((t_p.strftime("%j")))
            return self.get_files(year, day)[-1]
        else:
            return files[i - 1]

    def get_following_file(self, filename):
        """
        Return filename of the file that follows the given filename in time.

        Arguments:

            filename(str): The name of the file of which to find the following file.

        Returns:

            The filename of the file following the file with the given filename.

        """
        t = self.name_to_date(filename)

        year = t.year
        day  = int((t.strftime("%j")))
        files = self.get_files(year, day)

        i = files.index(filename)

        if i == len(files) - 1:
            dt = timedelta(days = 1)
            t_p = t + dt
            year = t_p.year
            day  = int((t_p.strftime("%j")))
            return self.get_files(year, day)[0]
        else:
            return files[i + 1]

    def get_files_in_range(self,
                           t0,
                           t1,
                           t0_inclusive = False,
                           t1_inclusive = False):
        """
        Get all files within time range.

        Retrieves a list of product files that include the specified
        time range.

        Arguments:

            t0(datetime.datetime): Start time of the time range

            t1(datetime.datetime): End time of the time range

            t0_inclusive(bool): Whether or not the list should start with
                the first file containing t0 (True) or the first file found
                with start time later than t0 (False).

        Returns:

            List of filename that include the specified time range.

        """
        dt = timedelta(days = 1)

        t = t0
        files = []

        while((t1 - t).total_seconds() > 0.0):

            year = t.year
            day  = int((t.strftime("%j")))

            fs = self.get_files(year, day)

            ts = [self.name_to_date(f) for f in fs]

            dts0 = [self.name_to_date(f) - t0 for f in fs]
            pos0 = [dt.total_seconds() >= 0.0 for dt in dts0]

            dts1 = [self.name_to_date(f) - t1 for f in fs]
            pos1 = [dt.total_seconds() > 0.0 for dt in dts1]

            inds = [i for i, (p0, p1) in enumerate(zip(pos0, pos1)) if p0 and not p1]
            files += [fs[i] for i in inds]

            t += dt

        # Make sure that we have a least one file even if none
        # start within given range.
        if len(files) < 1:
            # Get current and following day.
            y0 = t0.year
            d0 = t0.timetuple().tm_yday
            t = t + dt
            y1 = t.year
            d1 = t.timetuple().tm_yday

            fs = self.get_files(y0, d0)
            fs += self.get_files(y1, d1)

            dts = [(self.name_to_date(f) - t0).total_seconds() for f in fs]
            ind = np.argmin(np.abs(np.array(dts)))
            files = [fs[ind]]

        if t0_inclusive and not files == []:
            f_p = self.get_preceeding_file(files[0])
            files = [f_p] + files

        if not files == [] and not pos1[-1]:
            files += [self.get_following_file(files[-1])]

        if t1_inclusive and not files == []:
            files += [self.get_following_file(files[-1])]

        return files

    def get_file_by_date(self, t):
        """
        Get file with start time closest to a given date.

        Arguments:

            t(datetime): A date to look for in a file.

        Return:

            The filename of the file with the closest start time
            before the given time.
        """

        # Check last file from previous day
        dt = timedelta(days = 1)
        t_p = t - dt
        year = t_p.year
        day  = int((t_p.strftime("%j")))
        files = self.get_files(year, day)[-1:]

        year = t.year
        day  = int(t.strftime("%j"))
        files += self.get_files(year, day)

        ts  = [self.name_to_date(f) for f in files]
        dts = [tf - t for tf in ts]
        dts = np.array([dt.total_seconds() for dt in dts])
        inds = np.argsort(dts)
        indices = np.where(dts[inds] < 0.0)[0]

        if len(indices) == 0:
            ind = len(dts) - 1
        else:
            ind = inds[indices[-1]]

        return files[ind]

    def download_file(self, filename):
        """
        Download a given product file.

        Arguments:

            filename(str): The name of the file to download.

            dest(str): Where to store the file.
        """
        cache_hit = file_cache.get(filename)
        if not cache_hit is None:
            return cache_hit
        else:
            date = self.name_to_date(filename)
            filename = ensure_extension(filename, [".hdf", "HDF5"])
            dest     = os.path.join(file_cache.path, filename)
            self.download(filename, dest)

        return dest

################################################################################
# NASA Gesdisc GPM products
################################################################################

class GesdiscProduct(DataProduct):
    """
    Base class for data products available from the NASA gesdisc https server.
    """
    base_url = "gpm1.gesdisc.eosdis.nasa.gov"

    def __init__(self, level, product):
        super().__init__()
        self.prog    = re.compile('"[^"]*.HDF5"')
        self.level   = level
        self.product = product

    @property
    def _request_string(self):
        base_url = "https://gpm1.gesdisc.eosdis.nasa.gov/data/{level}/{product}"
        base_url = base_url.format(level = self.level, product = self.product)
        return base_url + "/{year}/{day}/{filename}"


    def get_files(self, year, day):

        day = str(day)
        day = "0" * (3 - len(day)) + day
        c = http.client.HTTPSConnection("gpm1.gesdisc.eosdis.nasa.gov")

        request_string = self._request_string.format(year = year, day = day, filename = "")
        c.request("GET", request_string)
        r = c.getresponse()
        r = str(r.read())

        files = list(set(self.prog.findall(r)))
        files.sort()
        return [f[1:-1] for f in files]

    def name_to_date(self, filename):
        s = filename.split(".")[4]
        t = datetime.strptime(s[:16], "%Y%m%d-S%H%M%S")
        return t

    def download(self, filename, dest):
        t = self.name_to_date(filename)
        year = t.year
        day  = t.strftime("%j")
        day  = "0" * (3 - len(day)) + day

        request_string = self._request_string.format(year = year, day = day, filename = filename)


        r = requests.get(request_string)
        with open(dest, 'wb') as f:
            for chunk in r:
                f.write(chunk)

################################################################################
# Products from ICARE server
################################################################################

class IcareProduct(DataProduct):

    """
    Base class for data products available from the ICARE ftp server.
    """
    base_url = "ftp.icare.univ-lille1.fr"

    def __init__(self, product_path, name_to_date):
        """
        Create a new product instance.

        Arguments:

        product_path(str): The path of the product. This should point to
            the folder that bears the product name and contains the directory
            tree which contains the data files sorted by date.

        name_to_date(function): Funtion to convert filename to datetime object.
        """
        self.product_path = product_path
        self._name_to_date = name_to_date
        self.cache = {}


    def __ftp_listing_to_list__(self, path, t = int):
        """
        Retrieve directory content from ftp listing as list.

        Arguments:

           path(str): The path from which to retrieve the ftp listing.

           t(type): Type constructor to apply to the elements of the
                listing. To retrieve a list of strings use t = str.

        Return:

            A list containing the content of the ftp directory.

        """
        if not path in self.cache:
            with FTP(IcareProduct.base_url) as ftp:
                ftp.login(user = settings.logins["icare"][0],
                          passwd = settings.logins["icare"][1])
                try:
                    ftp.cwd(path)
                except:
                    raise Exception("Can't find product folder " + path  +
                                    "on the ICARE ftp server.. Are you sure this is"
                                    "a  ICARE multi sensor product?")
                ls = ftp.nlst()
            ls = [t(l) for l in ls]
            self.cache[path] = ls
        return self.cache[path]

    def name_to_date(self, filename):
        return self._name_to_date(filename)

    def get_files(self, year, day):
        """
        Return all files from given year and julian day. Files are returned
        in chronological order sorted by the file timestamp.

        Arguments:

            year(int): The year from which to retrieve the filenames.

            day(int): Day of the year of the data from which to retrieve the
                the filenames.

        Return:

            List of all HDF files available of this product on the given date.
        """
        day_str = str(day)
        day_str = "0" * (3 - len(day_str)) + day_str
        date = datetime.strptime(str(year) + str(day_str), "%Y%j")
        path = os.path.join(self.product_path, str(year),
                            date.strftime("%Y_%m_%d"))
        ls = self.__ftp_listing_to_list__(path, str)
        files = [l for l in ls if l[-3:] == "hdf"]
        return files

    def download(self, filename, dest):
        date = self.name_to_date(filename)
        path = os.path.join(self.product_path, str(date.year),
                            date.strftime("%Y_%m_%d"))

        with FTP(self.base_url) as ftp:
            ftp.logins(user = settings.logins["icare"][0],
                       passwd = settings.logins["icare"][1])
            ftp.cwd(path)
            with open(dest, 'wb') as f:
                ftp.retrbinary('RETR ' + filename, f.write)

################################################################################
# Opera ground radar
################################################################################

class OperaRadar(DataProduct):
    import cartopy.crs as ccrs
    """
    Base class for data products available from the ICARE ftp server.
    """
    base_url = "https://geoservices.meteofrance.fr/services"
    def __init__(self, product):
        """
        Create a new product instance.

        Arguments:

        product_path(str): The path of the product. This should point to
            the folder that bears the product name and contains the directory
            tree which contains the data files sorted by date.

        name_to_date(function): Funtion to convert filename to datetime object.
        """
        self.product = product

        request = OperaRadar.base_url + "/GetAPIKey?username={name}&password={passwd}"
        name, passwd = settings.logins["opera"]
        request = request.format(name = name, passwd = passwd)
        c = http.client.HTTPSConnection("geoservices.meteofrance.fr")
        c.request("GET", request)
        r = c.getresponse().read().decode()
        root = ElementTree.fromstring(r)
        self.token = root.text

    def download(self, time, dest):
        c = http.client.HTTPSConnection("geoservices.meteofrance.fr")
        request = OperaRadar.base_url + "/odyssey?product={product}"
        request += "&time={time}&token={token}&format=HDF5"
        request = request.format(product = self.product,
                                 time = time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                 token = self.token)
        c.request("GET", request)
        r = c.getresponse()
        with open(dest, 'wb') as f:
            f.write(r.read())
        return dest

    def download_file(self, filename):
        """
        Download a given product file.

        Arguments:

            filename(str): The name of the file to download.

            dest(str): Where to store the file.
        """
        cache_hit = file_cache.get(filename)
        if not cache_hit is None:
            return cache_hit
        else:
            date = self.name_to_date(filename)
            filename = ensure_extension(filename, [".hdf", "HDF5"])
            dest     = os.path.join(file_cache.path, filename)
            self.download(date, dest)
            time.sleep(5)
        return dest

    def get_files(self, year, day):
        """
        Return all files from given year and julian day. Files are returned
        in chronological order sorted by the file timestamp.

        Arguments:

            year(int): The year from which to retrieve the filenames.

            day(int): Day of the year of the data from which to retrieve the
                the filenames.

        Return:

            List of all HDF files available of this product on the given date.
        """
        files = []
        pattern = "OPERA_{}_{}_{}_{}_{}.hdf"
        for i in range(24):
            for j in range(4):
                files += [pattern.format(self.product,
                                         str(year).zfill(2),
                                         str(day).zfill(3),
                                         str(i).zfill(2),
                                         str(15 * j).zfill(2))]
        return files

    def name_to_date(self, name):
        s = "_".join(name.split("_")[-4:])
        return datetime.strptime(s.split(".")[0], "%Y_%j_%H_%M")

import http.client


################################################################################
# Filename to date conversion
################################################################################

def modis_name_to_date(s):
    """Convert MODIS filename to date"""
    i = s.index(".")
    s = s[i + 1 :]
    j = s.index(".")
    s = s[: j + 5]
    return datetime.strptime(s, "A%Y%j.%H%M")

def caliop_name_to_date(s):
    """Convert CALIOP name to date"""
    i = s.index(".")
    j = s[i + 1:].index(".") - 4
    s = s[i + 1 : i + j].replace("-", ".")
    return datetime.strptime(s, "%Y.%m.%dT%H.%M")

def dardar_name_to_date(s):
    """Convert DARDAR name to date"""
    date = s.split("_")[2]
    return datetime.strptime(date, "%Y%j%H%M%S")

def cloudsat_name_to_date(s):
    """Convert CLOUDSAT name to date"""
    s = os.path.basename(s)
    s = s.split("_")[0]
    return datetime.strptime(s, "%Y%j%H%M%S")

################################################################################
# Data products
################################################################################

caliop     = IcareProduct("SPACEBORNE/CALIOP/01kmCLay.v4.10", caliop_name_to_date)
dardar     = IcareProduct("SPACEBORNE/MULTI_SENSOR/DARDAR_CLOUD", dardar_name_to_date)
modis      = IcareProduct("SPACEBORNE/MODIS/MYD021KM", modis_name_to_date)
modis_geo  = IcareProduct("SPACEBORNE/MODIS/MYD03", modis_name_to_date)
cloudsat   = IcareProduct("SPACEBORNE/CLOUDSAT/2B-CLDCLASS.v05.06", cloudsat_name_to_date)
modis_terra     = IcareProduct("SPACEBORNE/MODIS/MOD021KM", modis_name_to_date)
modis_terra_geo = IcareProduct("SPACEBORNE/MODIS/MOD03", modis_name_to_date)

dpr_2a_gpr      = GesdiscProduct("GPM_L2", "GPM_2ADPR.06", )
gpm_2b_cmb      = GesdiscProduct("GPM_L2", "GPM_2BCMB.06")
gpm_2a_gprofgmi = GesdiscProduct("GPM_L2", "GPM_2AGPROFGPMGMI.05")
gpm_1c_r        = GesdiscProduct("GPM_L1C", "GPM_1CGPMGMI_R.05")

opera_rainfall = OperaRadar("RAINFALL_RATE")
opera_maximum_reflectivity = OperaRadar("MAXIMUM_REFLECTIVITY")
opera_rainfall_accumulation = OperaRadar("HOURLY_RAINFAL_ACCUMULATION")
