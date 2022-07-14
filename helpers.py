from qgis.core import *
from qgis.utils import Qgis


def get_layer_by_name(layer_name):
    """
    Fetches A QgsVectorLayer From The Project By Name
    """
    layers = QgsProject.instance().mapLayersByName(layer_name)
    if layers:
        required_layer = layers[0]
    else:
        required_layer = None
    return required_layer


def get_spatial_index(layer):
    """
    Create a spatial index for the provided layer

    param layer: QgsVectorLayer used to create the spatial index

    """
    layer_s_idx = QgsSpatialIndex(layer.getFeatures(),
                                  flags=QgsSpatialIndex.FlagStoreFeatureGeometries)
    return layer_s_idx


def clone_layer(layer, layer_name, copy_fields=False, fields_to_keep=None):
    """
    Create a clone of a given QgsVectorLayer
    """
    layer_type = QgsWkbTypes.displayString(QgsWkbTypes.flatType(int(layer.wkbType())))
    mem_layer = QgsVectorLayer(layer_type + "?crs=" + str(layer.sourceCrs().authid()),
                               layer_name,
                               "memory")
    if copy_fields:
        if fields_to_keep and isinstance(fields_to_keep, list):

            attr = [field for field in layer.dataProvider().fields().toList() if field.name() in fields_to_keep]
        else:
            attr = layer.dataProvider().fields().toList()
        mem_layer_data = mem_layer.dataProvider()

        mem_layer_data.addAttributes(attr)
        mem_layer.updateFields()

    return mem_layer


def get_blank_feature(layer_data_provider):
    """
    Create A Empty Feature For A Given VectorDataProvider
    """
    feature = QgsFeature()
    feature.setFields(layer_data_provider.fields())
    return feature


def set_layer_style(layer, qml_path):
    """
    Add A QML Style Sheet To The Layer From The Given Path
    """
    layer.loadNamedStyle(qml_path)


def add_layer_to_map(layer):
    """
    Add The Given QgsMapLayer To The Current Project
    """
    QgsProject.instance().addMapLayer(layer)


def display_info(iface, message:str):
    """
    Display info message in message bar
    :param iface: QgisInterface
    :param message: String to display
    :return:
    """
    message_bar = iface.messageBar().createMessage(message)
    iface.messageBar().pushWidget(message_bar, level=Qgis.Info, duration=2)


def display_warning(iface, message:str):
    """
    Display warning message inn message bar
    :param iface: QgisInterface
    :param message: String to display
    :return:
    """
    message_bar = iface.messageBar().createMessage(message)
    iface.messageBar().pushWidget(message_bar, level=Qgis.Warning, duration=2)