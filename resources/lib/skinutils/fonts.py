'''
Created on 09/08/2011

@author: mikel
'''
import os
import xbmc
import shutil
from skinutils import SkinUtilsError, check_skin_writability, reload_skin, try_remove_file, case_file_exists, DocumentCache, get_logger
import xml.etree.ElementTree as ET



class FontXmlError(SkinUtilsError):
    pass



class FontManager:
    __installed_names = None
    __installed_fonts = None
    __doc_cache = None


    def _list_skin_font_files(self):
        font_xml_list = []
        skin_path = xbmc.translatePath("special://skin/")

        #Go into each dir. Could be 720, 1080...
        for dir_item in os.listdir(skin_path):
            dir_path = os.path.join(skin_path, dir_item)
            if os.path.isdir(dir_path):
                #Try with font.xml
                file = os.path.join(dir_path, "font.xml")
                if case_file_exists(file):
                    font_xml_list.append(file)

                #Don't try the next step on windows, wasted time
                file = os.path.join(dir_path, "Font.xml")
                if case_file_exists(file):
                    font_xml_list.append(file)

        return font_xml_list


    def __init__(self):
        self.__installed_names = []
        self.__installed_fonts = []
        self.__doc_cache = DocumentCache()

        #Check if the environment is sane
        check_skin_writability()

        #Initialize the doc cache with the skin's files
        for file in self._list_skin_font_files():
            self.__doc_cache.add(file)


    def is_name_installed(self, name):
        return name in self.__installed_names


    def is_font_installed(self, file):
        return file in self.__installed_fonts


    def _get_font_attr(self, node, name):
        attrnode = node.find(name)
        if attrnode is not None:
            return attrnode.text


    def _copy_font_file(self, file):
        skin_font_path = xbmc.translatePath("special://skin/fonts/")
        file_name = os.path.basename(file)
        dest_file = os.path.join(skin_font_path, file_name)

        #TODO: Unix systems could use symlinks

        #Check if it's already there
        if dest_file not in self.__installed_fonts:
            self.__installed_fonts.append(dest_file)

            #Overwrite if file exists
            shutil.copyfile(file, dest_file)


    def _add_font_attr(self, fontdef, name, value):
        attr = ET.SubElement(fontdef, name)
        attr.text = value
        attr.tail = "\n\t\t\t"
        return attr


    def _install_font_def(self, skin_file, name, filename, size, style="", aspect="", linespacing=""):
        #Add it to the registry
        self.__installed_names.append(name)

        #Get the parsed skin font file
        font_doc = self.__doc_cache.read(skin_file)

        #Iterate over all the fontsets on the file
        for fontset in font_doc.getroot().findall("fontset"):
            fontset.findall("font")[-1].tail = "\n\t\t"
            fontdef = ET.SubElement(fontset, "font")
            fontdef.text, fontdef.tail = "\n\t\t\t", "\n\t"

            self._add_font_attr(fontdef, "name", name)

            #We get the full file path to the font, so let's basename
            self._add_font_attr(fontdef, "filename", os.path.basename(filename))
            self._copy_font_file(filename)

            last = self._add_font_attr(fontdef, "size", size)

            if style:
                if style in ["normal", "bold", "italics", "bolditalics"]:
                    last = self._add_font_attr(fontdef, "style", style)

                else:
                    raise FontXmlError(
                        "Font '%s' has an invalid style definition: %s"
                        % (name, style)
                    )

            if aspect:
                last = self._add_font_attr(fontdef, "aspect", aspect)

            if linespacing:
                last = self._add_font_attr(fontdef, "linespacing", linespacing)

            last.tail = "\n\t\t"


    def _install_file(self, doc_cache, user_file, skin_file, font_path):
        user_doc = doc_cache.read(user_file)

        #Handle only the first fontset
        fontset = user_doc.getroot().find("fontset")
        if len(fontset):
            #Every font definition inside it
            for item in fontset.findall("font"):
                name = self._get_font_attr(item, "name")

                #Basic check for malformed defs.
                if name is None:
                    raise FontXmlError("Malformed XML: No name for font definition.")

                #Omit already defined fonts
                elif not self.is_name_installed(name):
                    font_file_path = os.path.join(
                        font_path, self._get_font_attr(item, "filename")
                    )
                    self._install_font_def(
                        skin_file,
                        name,
                        font_file_path,
                        self._get_font_attr(item, "size"),
                        self._get_font_attr(item, "style"),
                        self._get_font_attr(item, "aspect"),
                        self._get_font_attr(item, "linespacing")
                    )


    def _get_res_folder(self, path):
        return os.path.basename(os.path.dirname(path))


    def _get_res_filename(self, res_folder, user_file):
        path, ext = os.path.splitext(user_file)
        return path + '-' + res_folder + ext


    def install_file(self, user_file, font_path, commit=True, clear=True):
        doc_cache = DocumentCache()

        #If the file does not exist the following will fail
        doc_cache.add(user_file)

        #Install the file into every cached skin font file
        for skin_file in self.__doc_cache.list_files():
            res_folder = self._get_res_folder(skin_file)
            res_file = self._get_res_filename(res_folder, user_file)

            #If an specific res file exists...
            if os.path.isfile(res_file):
                self._install_file(doc_cache, res_file, skin_file, font_path)

            #Otherwise use the dafault fallback
            else:
                self._install_file(doc_cache, user_file, skin_file, font_path)

        #If save was requested
        if commit:
            self.__doc_cache.write_all()

            #Clear cached docs after write (if requested)
            if clear:
                self.__doc_cache.clear_all()


    def remove_font(self, name):
        pass


    def remove_installed_names(self):
        self.__doc_cache.rollback_all()


    def remove_installed_fonts(self):
        for item in self.__installed_fonts:
            if not try_remove_file(item):
                get_logger().error(
                    'Failed removing font file "%s". XBMC may still be using it.' % item
                )


    def cleanup(self):
        self.remove_installed_names()

        #Reload skin so font files are no longer in use, and then delete them
        reload_skin()
        self.remove_installed_fonts()


    def __del__(self):
        self.cleanup()
