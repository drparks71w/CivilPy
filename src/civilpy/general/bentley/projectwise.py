# -*- coding: utf-8 -*-
"""
This script provides a library for interacting with the native ProjectWise API
(dmscli.dll, dmawin.dll) from Python.

It includes a PW_SESSION context manager to handle safe login/logout, and
functions for building an in-memory map of the project structure for fast lookups.
"""
import ctypes
import ctypes.wintypes
import os
import winreg

# --- Constants (equivalent to PWConstants class) ---
AAMODULE_ALL = 0
IDOK = 1

# Login Flags
AALOGIN_NO_DS_SELECT = 0x00000002
AALOGIN_SILENT = 0x00000020

# Project Property IDs
PROJ_PROP_ID = 1
PROJ_PROP_NAME = 12
PROJ_PROP_DESC = 13
PROJ_PROP_CREATORID = 5
PROJ_PROP_UPDATERID = 6
PROJ_PROP_CREATE_TIME = 16
PROJ_PROP_UPDATE_TIME = 17

# User Property IDs
USER_PROP_NAME = 2

# --- Globals for DLLs and State Management ---
dmscli = None
dmawin = None
_PW_DLLS_LOADED = False
_PW_API_INITIALIZED = False


class PW_SESSION:
    """
    A context manager to handle ProjectWise API login and logout.

    Usage:
        with PW_SESSION() as s: # Defaults to the ODOT datasource
            # Your PW API calls go here
            pass
    """

    def __init__(self, datasource_name="OhioDOT-pw.bentley.com:OhioDOT-pw-02"):
        """
        Initializes the session with a datasource name.

        Args:
            datasource_name (str, optional): The datasource to connect to.
                                             Defaults to "OhioDOT-pw.bentley.com:OhioDOT-pw-02".
        """
        self.datasource_name = datasource_name
        self.active_ds_handle = None

    def __enter__(self):
        """Called when entering the 'with' block. Handles DLL loading, API init, and login."""
        global _PW_API_INITIALIZED

        if not _PW_DLLS_LOADED:
            load_pw_dlls()

        if not _PW_API_INITIALIZED:
            print("Initializing ProjectWise API...")
            if not dmscli.aaApi_Initialize(AAMODULE_ALL):
                raise ConnectionError("Failed to initialize ProjectWise API.")
            _PW_API_INITIALIZED = True
            print("API Initialized.")

        print(f"Attempting silent login to '{self.datasource_name}'...")
        login_flags = AALOGIN_NO_DS_SELECT | AALOGIN_SILENT
        result = dmawin.aaApi_LoginDlgExt(None, None, login_flags, self.datasource_name, len(self.datasource_name) + 1,
                                          None, None, None)

        if ctypes.c_void_p(result).value != IDOK:
            raise ConnectionError("Silent login failed. Ensure ProjectWise Explorer is running and you are logged in.")

        print("Login successful.")
        self.active_ds_handle = dmscli.aaApi_GetActiveDatasource()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Called when exiting the 'with' block. Handles logout."""
        if self.active_ds_handle:
            print("\nLogging out...")
            dmscli.aaApi_LogoutByHandle(self.active_ds_handle)
            print("Logged out.")
            self.active_ds_handle = None


def get_pw_path():
    """Finds the ProjectWise installation path by searching the Windows Registry."""
    reg_keys_to_check = [
        ("SOFTWARE\\Bentley\\ProjectWise\\ProjectWise Explorer", None),
        ("SOFTWARE\\Bentley\\ProjectWise Explorer", None),
        ("SOFTWARE\\Wow6432Node\\Bentley\\ProjectWise Explorer", None)
    ]
    for key_path, subkey_path in reg_keys_to_check:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                try:
                    path, _ = winreg.QueryValueEx(key, "PathName")
                    if path: return path
                except FileNotFoundError:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        subkey_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            try:
                                path, _ = winreg.QueryValueEx(subkey, "PathName")
                                if path: return path
                            except FileNotFoundError:
                                continue
        except FileNotFoundError:
            continue
    raise FileNotFoundError("Could not find ProjectWise installation path in the registry.")


def load_pw_dlls():
    """Finds the PW bin directory and loads the necessary DLLs, defining function prototypes."""
    global dmscli, dmawin, _PW_DLLS_LOADED
    if _PW_DLLS_LOADED: return True

    try:
        pw_install_path = get_pw_path()
        bin_path = os.path.join(pw_install_path, "bin")
        if not os.path.isdir(bin_path):
            raise NotADirectoryError(f"ProjectWise bin directory not found: {bin_path}")

        if hasattr(os, 'add_dll_directory'):
            os.add_dll_directory(bin_path)
        else:
            os.environ['PATH'] = bin_path + os.pathsep + os.environ['PATH']

        print("Loading ProjectWise DLLs...")
        dmscli = ctypes.WinDLL(os.path.join(bin_path, "dmscli.dll"))
        dmawin = ctypes.WinDLL(os.path.join(bin_path, "dmawin.dll"))

        # --- Define Function Prototypes ---
        dmscli.aaApi_Initialize.argtypes = [ctypes.wintypes.ULONG];
        dmscli.aaApi_Initialize.restype = ctypes.wintypes.BOOL
        dmawin.aaApi_LoginDlgExt.argtypes = [ctypes.wintypes.HWND, ctypes.c_wchar_p, ctypes.wintypes.ULONG,
                                             ctypes.c_wchar_p, ctypes.c_int, ctypes.c_wchar_p, ctypes.c_wchar_p,
                                             ctypes.c_wchar_p];
        dmawin.aaApi_LoginDlgExt.restype = ctypes.c_void_p
        dmscli.aaApi_GetProjectNamePath2.argtypes = [ctypes.c_long, ctypes.wintypes.BOOL, ctypes.c_wchar,
                                                     ctypes.c_wchar_p, ctypes.c_long];
        dmscli.aaApi_GetProjectNamePath2.restype = ctypes.wintypes.BOOL
        dmscli.aaApi_GetActiveDatasource.argtypes = [];
        dmscli.aaApi_GetActiveDatasource.restype = ctypes.c_void_p
        dmscli.aaApi_LogoutByHandle.argtypes = [ctypes.c_void_p];
        dmscli.aaApi_LogoutByHandle.restype = ctypes.wintypes.BOOL
        dmscli.aaApi_GetProjectIdByNamePath.argtypes = [ctypes.c_wchar_p];
        dmscli.aaApi_GetProjectIdByNamePath.restype = ctypes.c_long
        dmscli.aaApi_SelectProject.argtypes = [ctypes.c_long];
        dmscli.aaApi_SelectProject.restype = ctypes.c_long
        dmscli.aaApi_GetProjectNumericProperty.argtypes = [ctypes.c_long, ctypes.c_long];
        dmscli.aaApi_GetProjectNumericProperty.restype = ctypes.c_long
        dmscli.aaApi_GetProjectStringProperty.argtypes = [ctypes.c_long, ctypes.c_long];
        dmscli.aaApi_GetProjectStringProperty.restype = ctypes.c_wchar_p
        dmscli.aaApi_SelectUser.argtypes = [ctypes.c_long];
        dmscli.aaApi_SelectUser.restype = ctypes.c_long
        dmscli.aaApi_GetUserStringProperty.argtypes = [ctypes.c_long, ctypes.c_long];
        dmscli.aaApi_GetUserStringProperty.restype = ctypes.c_wchar_p
        # Prototypes for buffer-based folder searching
        dmscli.aaApi_SelectProjectDataBufferChilds2.argtypes = [ctypes.c_long, ctypes.wintypes.BOOL];
        dmscli.aaApi_SelectProjectDataBufferChilds2.restype = ctypes.c_void_p
        dmscli.aaApi_DmsDataBufferGetCount.argtypes = [ctypes.c_void_p];
        dmscli.aaApi_DmsDataBufferGetCount.restype = ctypes.c_long
        dmscli.aaApi_DmsDataBufferGetNumericProperty.argtypes = [ctypes.c_void_p, ctypes.c_long, ctypes.c_long];
        dmscli.aaApi_DmsDataBufferGetNumericProperty.restype = ctypes.c_long
        dmscli.aaApi_DmsDataBufferGetStringProperty.argtypes = [ctypes.c_void_p, ctypes.c_long, ctypes.c_long];
        dmscli.aaApi_DmsDataBufferGetStringProperty.restype = ctypes.c_wchar_p
        dmscli.aaApi_DmsDataBufferFree.argtypes = [ctypes.c_void_p];
        dmscli.aaApi_DmsDataBufferFree.restype = None

        _PW_DLLS_LOADED = True
        print("DLLs loaded successfully.")
        return True
    except Exception as e:
        print(f"Error loading ProjectWise DLLs: {e}")
        _PW_DLLS_LOADED = False
        return False


def _build_map_recursive(start_folder_id, current_map_level, flat_pid_map, path_context, current_depth, max_depth):
    """Internal recursive function to build the project map."""
    if current_depth > max_depth:
        return

    child_buffer = dmscli.aaApi_SelectProjectDataBufferChilds2(start_folder_id, False)
    if not child_buffer:
        return

    try:
        child_count = dmscli.aaApi_DmsDataBufferGetCount(child_buffer)
        for i in range(child_count):
            child_name = dmscli.aaApi_DmsDataBufferGetStringProperty(child_buffer, PROJ_PROP_NAME, i)
            child_id = dmscli.aaApi_DmsDataBufferGetNumericProperty(child_buffer, PROJ_PROP_ID, i)

            # Add to the hierarchical map
            current_map_level[child_name] = {'id': child_id}

            # If this is a PID folder (level 4), add it to the flat lookup map
            if current_depth == 3:  # District is 1, County is 2, PID is 3
                pid = child_name
                flat_pid_map[pid] = {
                    'id': child_id,
                    'project_type': path_context[0],
                    'district': path_context[1],
                    'county': path_context[2]
                }

            # Recurse into the subfolder
            _build_map_recursive(child_id, current_map_level[child_name], flat_pid_map, path_context + [child_name],
                                 current_depth + 1, max_depth)
    finally:
        dmscli.aaApi_DmsDataBufferFree(child_buffer)


def build_project_map(max_depth=4):
    """
    Builds an in-memory map of the ProjectWise folder structure for fast lookups.

    Args:
        max_depth (int): How many levels deep to map the folder structure.

    Returns:
        tuple: A tuple containing two dictionaries:
               (hierarchical_map, flat_pid_map)
    """
    if not dmscli: raise RuntimeError("ProjectWise DLLs are not loaded.")

    print("Building project map... this may take some time.")

    hierarchical_map = {}
    flat_pid_map = {}

    root_folders_to_map = ["01 Active Projects", "02 Sold Projects"]

    for root_name in root_folders_to_map:
        root_id = dmscli.aaApi_GetProjectIdByNamePath(root_name)
        if root_id > 0:
            print(f"Mapping '{root_name}'...")
            hierarchical_map[root_name] = {'id': root_id}
            _build_map_recursive(root_id, hierarchical_map[root_name], flat_pid_map, [root_name], 1, max_depth)
        else:
            print(f"Warning: Could not find root folder '{root_name}'.")

    print("Project map built successfully.")
    return hierarchical_map, flat_pid_map


def get_user_name(user_id):
    """Helper function to retrieve a user's name from their ID."""
    if user_id <= 0: return "N/A"
    if dmscli.aaApi_SelectUser(user_id) == 1:
        return dmscli.aaApi_GetUserStringProperty(USER_PROP_NAME, 0)
    return "Unknown User"


def get_project_properties(project_id):
    """Selects a project and extracts a dictionary of its key metadata."""
    properties = {}
    if dmscli.aaApi_SelectProject(project_id) == 1:
        properties['Project ID'] = project_id
        properties['Name'] = dmscli.aaApi_GetProjectStringProperty(PROJ_PROP_NAME, 0)
        properties['Description'] = dmscli.aaApi_GetProjectStringProperty(PROJ_PROP_DESC, 0)
        properties['Created On'] = dmscli.aaApi_GetProjectStringProperty(PROJ_PROP_CREATE_TIME, 0)
        properties['Updated On'] = dmscli.aaApi_GetProjectStringProperty(PROJ_PROP_UPDATE_TIME, 0)
        creator_id = dmscli.aaApi_GetProjectNumericProperty(PROJ_PROP_CREATORID, 0)
        properties['Created By'] = get_user_name(creator_id)
        updater_id = dmscli.aaApi_GetProjectNumericProperty(PROJ_PROP_UPDATERID, 0)
        properties['Updated By'] = get_user_name(updater_id)
        return properties
    return None


def display_project_properties(properties):
    """Nicely prints the dictionary of project properties."""
    if not properties:
        print("Could not retrieve project properties.")
        return
    print("\n--- Project Metadata ---")
    for key, value in properties.items():
        display_value = value if value else "Not Set"
        print(f"{key + ':':<15} {display_value}")
    print("-" * 26)


# --- Example Usage ---
# This block demonstrates how to use the library to build the map and then query it.
if __name__ == "__main__":
    try:
        # Use the context manager to handle login/logout with the default datasource
        with PW_SESSION() as s:
            # 1. Build the map of the project structure into memory
            hierarchy_map, pid_lookup_map = build_project_map()

            # 2. Now you can perform fast lookups using the pid_lookup_map
            print("\n--- Performing fast lookups using the in-memory map ---")
            pids_to_find = ["113849", "105151", "999999"]  # Example list

            for pid in pids_to_find:
                print(f"\n=======================================")
                print(f"Looking up PID: {pid}")

                if pid in pid_lookup_map:
                    project_info = pid_lookup_map[pid]
                    project_id = project_info['id']

                    print(f"SUCCESS: Found Project ID: {project_id}")
                    print(
                        f"  From Path: {project_info['project_type']} > {project_info['district']} > {project_info['county']}")

                    # Get and display the rest of the metadata
                    properties = get_project_properties(project_id)
                    display_project_properties(properties)
                else:
                    print(f"FAILURE: PID {pid} not found in the project map.")
            print(f"=======================================")

    except (ConnectionError, RuntimeError, FileNotFoundError) as e:
        print(f"\nERROR: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")