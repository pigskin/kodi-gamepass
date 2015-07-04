'''
Created on 09/08/2011

@author: mikel
'''
__all__ = ["fonts", "includes"]


import os
from os import listdir
from os.path import isdir, isfile, dirname, basename
import sys
import time
import xbmc, xbmcgui
import shutil
import re
from datetime import datetime
import xml.etree.ElementTree as ET
import logging



class SkinUtilsError(Exception):
    pass


def reload_skin():
    xbmc.executebuiltin("XBMC.ReloadSkin()")


def setup_logging():
    #Keep comaptibility with Python2.6
    if hasattr(logging, 'NullHandler'):
        logger = logging.getLogger('skinutils')
        logger.addHandler(logging.NullHandler())


def get_logger():
    return logging.getLogger('skinutils')


def debug_log(msg):
    get_logger().debug(msg)


def get_sha1_obj():
    #SHA1 lib 2.4 compatibility
    try:
        from hashlib import sha1
        return sha1()
    except:
        import sha
        return sha.new()


def sha1_file(file, block_size=2**20):
    f = open(file, 'rb')
    sha1 = get_sha1_obj()

    while True:
        data = f.read(block_size)
        if not data:
            break
        sha1.update(data)

    f.close()

    return sha1.hexdigest()


def try_remove_file(file, wait=0.5, tries=10):
    removed = False
    num_try = 0

    while num_try < tries and not removed:
        try:
            os.remove(file)
            return True

        except OSError:
            num_try += 1
            time.sleep(wait)

    return False


def case_file_exists(file):
    if not os.path.isfile(file):
        return False

    else:
        file_dir = dirname(file)
        if not isdir(file_dir):
            return False

        else:
            dir_contents = listdir(file_dir)
            return basename(file) in dir_contents


def get_current_skin_path():
    return os.path.normpath(xbmc.translatePath("special://skin/"))


def get_skin_name():
    return os.path.basename(get_current_skin_path())


def get_local_skin_path():
    user_addons_path = xbmc.translatePath("special://home/addons")
    return os.path.normpath(
        os.path.join(user_addons_path, get_skin_name())
    )


def copy_skin_to_userdata(ask_user=True):
    #Warn user before doing this weird thing
    d = xbmcgui.Dialog()
    msg1 = "This addon needs to install some extra resources."
    msg2 = "This installation requires a manual XBMC restart."
    msg3 = "Begin installation now? After that it will exit."

    make_copy = (
        not ask_user or
        d.yesno("Notice", msg1, msg2, msg3)
    )

    if make_copy:
        #Get skin dest name
        local_skin_path = get_local_skin_path()

        #If it was not copied before...
        if not os.path.exists(local_skin_path):
            shutil.copytree(get_current_skin_path(), local_skin_path)

    return make_copy


def is_invalid_local_skin():
    #Get skin paths
    current_skin_path = get_current_skin_path()
    local_skin_path = get_local_skin_path()

    #If the local path does not exist
    if not os.path.isdir(local_skin_path):
        return False

    else:
        #Get addon xml paths
        current_xml = os.path.join(current_skin_path, 'addon.xml')
        local_xml = os.path.join(local_skin_path, 'addon.xml')

        #Both files must exist
        if not os.path.isfile(current_xml) or not os.path.isfile(local_xml):
            return True

        #If sum of both files mismatch, got it!
        elif sha1_file(current_xml) != sha1_file(local_xml):
            return True

        #Otherwise everything is ok
        else:
            return False


def fix_invalid_local_skin():
    local_skin_path = get_local_skin_path()
    time_suffix = datetime.now().strftime('%Y%m%d%H%M%S')
    backup_skin_path = local_skin_path + '-skinutils-' + time_suffix

    #Just move the skin, if it already exists someone is trolling us...
    shutil.move(local_skin_path, backup_skin_path)

    #And now do the real copy
    copy_skin_to_userdata(ask_user=False)

    #Inform the user about the operation...
    d = xbmcgui.Dialog()
    l1 = "Your local skin is not in use (probably outdated)."
    l2 = "Press OK to apply a fix (archiving the old skin)."
    l3 = "You will need to restart XBMC once more."
    d.ok("Notice", l1, l2, l3)
    sys.exit()


#Skin was copied but XBMC was not restarted
def check_needs_restart():
    #Get skin paths
    current_skin_path = get_current_skin_path()
    local_skin_path = get_local_skin_path()

    #Local skin exists and does not match current skin path
    if os.path.isdir(local_skin_path) and current_skin_path != local_skin_path:
        #Check if the local skin is a leftover from a previous XBMC install
        if is_invalid_local_skin():
            fix_invalid_local_skin()

        #Local skin is correct, a restart is needed
        else:
            d = xbmcgui.Dialog()
            d.ok("Notice", "Restart XBMC to complete the installation.")
            sys.exit()


def do_write_test(path):
    test_file = os.path.join(path, 'write_test.txt')
    get_logger().debug('performing write test: %s' % test_file)

    try:
        #Open and cleanup
        open(test_file,'w').close()
        os.remove(test_file)
        return True

    except Exception:
        return False


def skin_is_local():
    return get_current_skin_path() == get_local_skin_path()


def check_skin_writability():
    #Some debug info
    debug_log("-- skinutils debug info --")
    debug_log("current skin path: %s\n" % get_current_skin_path())
    debug_log("local path should be: %s" % get_local_skin_path())

    #Check if XBMC needs a restart
    check_needs_restart()

    #Get the current skin's path
    skin_path = get_local_skin_path()

    #Check if it's local or not (contained in userdata)
    if not skin_is_local():
        copy_skin_to_userdata()
        sys.exit()

    #Check if this path is writable
    elif not os.access(skin_path, os.W_OK) or not do_write_test(skin_path):
        raise IOError("Skin directory is not writable.")


def make_backup(path):
    backup_path = path + '-skinutilsbackup'
    #If the backup already exists, don't overwrite it
    if not os.path.exists(backup_path):
        shutil.copy(path, backup_path)


def restore_backup(path):
    backup_path = path + '-skinutilsbackup'

    #Do nothing if no backup exists
    if os.path.exists(backup_path):

        #os.rename is atomic on unix, and it will overwrite silently
        if os.name != 'nt':
            os.rename(backup_path, path)

        #Windows will complain if the file exists
        else:
            os.remove(path)
            os.rename(backup_path, path)


def is_invalid_xml(file):

    contents = open(file, 'r').read()

    #Check for invalid comments
    pattern = re.compile('<!--(.*?)-->', re.MULTILINE | re.DOTALL)
    group_pattern = re.compile('^-|--|-$')
    for match in re.finditer(pattern, contents):
        if re.match(group_pattern, match.group(1)) is not None:
            return True

    #Check also for whitespace prior to declaration
    whitespace_pattern = re.compile('^\s+', re.MULTILINE)
    return whitespace_pattern.match(contents) is not None


def sanitize_xml(file):
    contents = open(file, 'r').read()

    #Remove leading whitespace to declaration
    contents = contents.lstrip()

    #Strip invalid comments
    p = re.compile('<!--.*?-->', re.MULTILINE | re.DOTALL)
    clean_contents, num_repl = re.subn(p, '', contents)

    open(file, 'w').write(clean_contents)


def install_resources():
    pass


class DocumentCache:
    __cached_docs = None


    def __init__(self):
        self.__cached_docs = {}


    def _check_file_exists(self, file):
        if not os.path.isfile(file):
            raise IOError('File not found: %s' % file)


    def contains(self, file):
        return file in self.__cached_docs


    def _check_file_known(self, file):
        if not self.contains(file):
            raise KeyError('Unknown file: %s' % file)


    def list_files(self):
        return self.__cached_docs.keys()


    def items(self):
        return self.__cached_docs.items()


    def add(self, file):
        self._check_file_exists(file)
        self.__cached_docs[file] = None


    def read(self, file):
        self._check_file_exists(file)

        #If there is no cached data...
        if not self.contains(file) or self.__cached_docs[file] is None:
            #Check if the file about to load is sane
            if is_invalid_xml(file):
                make_backup(file)
                sanitize_xml(file)

            #Parse the document
            self.__cached_docs[file] = ET.parse(file)

        return self.__cached_docs[file]


    def write(self, file):
        self._check_file_known(file)

        #If there is a document in cache it may contain modifications
        if self.__cached_docs[file] is not None:
            make_backup(file)
            self.__cached_docs[file].write(file)


    def write_all(self):
        for item in self.__cached_docs:
            self.write(item)


    def clear(self, file):
        self._check_file_known(file)
        self.__cached_docs[file] = None


    def clear_all(self):
        for item in self.__cached_docs:
            self.clear(item)


    def rollback(self, file):
        self._check_file_known(file)
        restore_backup(file)
        self.clear(file)


    def rollback_all(self):
        for item in self.__cached_docs:
            self.rollback(item)


setup_logging()
