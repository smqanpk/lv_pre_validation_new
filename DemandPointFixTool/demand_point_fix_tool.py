from PyQt5.Qt import QMenu, QTimer, QAction, QIcon, QToolButton, Qt, QSettings, QObject, pyqtSignal, QMessageBox, QEventLoop
import os
from qgis.PyQt.QtWidgets import QAction, QFileDialog
import configparser
from .demand_point_dialog import DemandPointToolDialog
import csv

from qgis.core import *
from ..helpers import *


class DemandPointFixTool(object):

    TOOL_NAME = "DemandPointFixTool"

    def __init__(self, iface, toolbar):
        self.iface = iface
        self.toolbar = toolbar
        self.menu = None
        self.tool_button = None
        # Init Layers
        self.layer_demand_points = None
        self.layer_lv_ug = None
        self.layer_lv_oh = None
        self.layer_lv_ug_sp_idx = None
        self.layer_lv_oh_sp_idx = None
        self.configurations = None

        self.first_start  = True
        self.dlg          = None
        self.errors_layer = None
        self.configurations_path = os.path.join(os.path.dirname(__file__), 'conf.ini')
        self.error_style_path = os.path.join(os.path.dirname(__file__), 'styles', 'errors.qml')
        # Enable Tool By Default
        self.init_configurations()
        self.enable_tool()

    def enable_tool(self):
        """
        Add tool to the toolbar menu
        """
        self.menu = self.create_sub_menu(self.TOOL_NAME)
        self.tool_button = self.add_toolbar_action(os.path.dirname(__file__) + '/icon.png', self.TOOL_NAME,
                                                   self.run)

    def remove_tool(self):
        """
        Remove tool from the toolbar
        :return:
        """
        self.disconnect_dialog_connections()
        if self.tool_button:
            self.toolbar.removeAction(self.tool_button)

    @staticmethod
    def create_sub_menu(name):
        """
        Create a sub menu
        :return:
        """
        return QMenu(name)

    def add_toolbar_action(self, icon_path, name, function, enabled=True):
        """
        Adds an action to the toolbar
        :param icon_path: path for the tool icon
        :param name: name of the action
        :param function: function called when the action is clicked
        :param enabled: action enabled by default set False to disable
        :return:
        """
        tool_button = QAction(QIcon(icon_path), name, self.iface.mainWindow())
        if not enabled:
            tool_button.setEnabled(False)
        tool_button.triggered.connect(function)
        self.toolbar.addAction(tool_button)
        return tool_button

    def init_configurations(self):
        self.configurations = configparser.ConfigParser()
        self.configurations.read(self.configurations_path)

    def init_used_layers(self):
        """

        """
        self.layer_demand_points = get_layer_by_name('Demand_Point')
        self.layer_lv_ug = get_layer_by_name('LV_UG_Conductor')
        self.layer_lv_oh = get_layer_by_name('LV_OH_Conductor')

    def check_layer_exist(self):
        """
        Check if the required layers are in the project
        """
        layers_to_check = [self.layer_demand_points,
                           self.layer_lv_oh,
                           self.layer_lv_ug]
        all_layers_exist = all([True if layer else False for layer in layers_to_check])
        return all_layers_exist

    def create_layer_spatial_indices(self):
        """
        Create spatial indices of the required layers
        """
        self.layer_lv_ug_sp_idx = get_spatial_index(self.layer_lv_ug)
        self.layer_lv_oh_sp_idx = get_spatial_index(self.layer_lv_oh)

    def get_non_intersecting_points(self):
        """
        Get All The Demand Points That Are Not Intersecting With The Wire Layers
        """

        # Iterate Over The Demand Features
        for feature in self.layer_demand_points.getFeatures():
            demand_point_geometry = feature.geometry()
            demand_point_geometry.convertToSingleType()
            demand_point = demand_point_geometry.asPoint()
            # Check If There Is A Wire In The Given Vicinity
            lv_ug_wires = self.layer_lv_ug_sp_idx.nearestNeighbor(demand_point, 1,
                                                                  float(self.configurations["DEFAULT"]['demand_fix_radius']))
            lv_oh_wires = self.layer_lv_oh_sp_idx.nearestNeighbor(demand_point, 1,
                                                                  float(self.configurations["DEFAULT"]['demand_fix_radius']))
            if not lv_oh_wires and not lv_ug_wires:
                continue
            # Check Non-Intersecting Wires
            int_lv_ug_wires = self.layer_lv_ug_sp_idx.intersects(demand_point_geometry.boundingBox())
            int_lv_oh_wires = self.layer_lv_oh_sp_idx.intersects(demand_point_geometry.boundingBox())
            if not int_lv_ug_wires and not int_lv_oh_wires:
                yield feature

    def create_errors_layer(self, error_features):
        """

        """
        errors_layer = clone_layer(self.layer_demand_points, "errors", copy_fields=True, fields_to_keep=["device_id"])
        errors_layer_dp = errors_layer.dataProvider()
        for feature in error_features:
            error_feature = get_blank_feature(errors_layer_dp)
            error_feature["device_id"] = feature["device_id"]
            error_point_geometry = feature.geometry()
            error_feature.setGeometry(error_point_geometry)
            errors_layer_dp.addFeatures([error_feature])
        set_layer_style(errors_layer, self.error_style_path)
        add_layer_to_map(errors_layer)
        return errors_layer

    def start_validation(self):

        self.init_used_layers()
        layers_exist = self.check_layer_exist()
        if not layers_exist:
            display_warning(self.iface, "The Required Layer Do Not Exist In The Project!")
            return
        self.create_layer_spatial_indices()
        error_features = self.get_non_intersecting_points()
        self.errors_layer = self.create_errors_layer(error_features)
        self.set_error_labels()
        display_info(self.iface, "Errors Layer Successfully Generated!")
        self.create_output_csv()

    def set_error_labels(self):
    
        error_feature_count = self.errors_layer.featureCount()
        self.dlg.err_dmd_pt.setText(str(error_feature_count))
        self.dlg.count_dmd_pt.setText(str(error_feature_count))

    def create_output_csv(self):
    
        out_csv_path = self.dlg.lineEdit_csv.text()
        if not out_csv_path:
            display_warning(self.iface, "No Output Path For The CSV Selected!")
            return
        request = QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry)
        errors_layer_dp = self.errors_layer.dataProvider()
        error_features = errors_layer_dp.getFeatures(request)
        with open(out_csv_path, 'w') as f:
            writer = csv.writer(f)

            # write a row to the csv
            headers = ['device_id', 'error']
            writer.writerow(headers)
            for error_feature in error_features:
                row = [error_feature['device_id'], 'is hanging or have a wrong flow direction.']
                writer.writerow(row)
        display_info(self.iface, "CSV File Successfully Exported")

    def select_output_file(self):
        filename, _filter = QFileDialog.getSaveFileName(
            self.dlg, "Select output file ","error_list.csv",'.csv')
        self.dlg.label_message.setText('Click Run QAQC to generate CSV file')
        if ".csv" in filename:
            self.dlg.lineEdit_csv.setText(filename)
        else:
            self.dlg.lineEdit_csv.setText(filename + '.csv')

    def init_dialog_connections(self):
        self.dlg.pushButton_qaqc.clicked.connect(self.start_validation)
        self.dlg.pushButton_csv.clicked.connect(self.select_output_file)

    def disconnect_dialog_connections(self):
        self.dlg.pushButton_qaqc.clicked.disconnect(self.start_validation)
        self.dlg.pushButton_csv.clicked.disconnect(self.select_output_file)

    def run(self):
        if self.first_start:
            self.dlg = DemandPointToolDialog()
            self.init_dialog_connections()
        self.dlg.show()



