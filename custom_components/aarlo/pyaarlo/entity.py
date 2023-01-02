import threading

from unidecode import unidecode

from .constant import (
    BATTERY_KEY,
    BATTERY_TECH_KEY,
    CHARGER_KEY,
    CHARGING_KEY,
    CONNECTION_KEY,
    CONNECTIVITY_KEY,
    DEVICE_KEYS,
    RESOURCE_KEYS,
    RESOURCE_UPDATE_KEYS,
    SIGNAL_STR_KEY,
    TIMEZONE_KEY,
    XCLOUD_ID_KEY,
)


class ArloEntity(object):
    """Base class for all Arlo entities, both physical devices and logical things
    like ArloLocation.

    Has code to handle providing common attributes and comment event handling.
    """

    def __init__(self, name, storage_id, arlo, attrs):
        self._name : str = name
        self._arlo = arlo
        self._attrs = attrs
        self._storage_id = storage_id

        self._lock = threading.Lock()
        self._attr_cbs_  = []

    def __repr__(self):
        # Representation string of object.
        return "<{0}:{1}:{2}>".format(
            self.__class__.__name__, self._storage_id, self._name
        )

    def _to_storage_key(self, attr):
        # Build a key incorporating the type!
        if isinstance(attr, list):
            return [self.__class__.__name__, self._storage_id] + attr
        else:
            return [self.__class__.__name__, self._storage_id, attr]

    def _event_handler(self, resource, event):
        self._arlo.vdebug("{}: got {} event **".format(self.name, resource))

        # Find properties. Event either contains a item called properties or it
        # is the whole thing.
        self.update_resources(event.get("properties", event))

    def _do_callbacks(self, attr, value):
        cbs = []
        with self._lock:
            for watch, cb in self._attr_cbs_:
                if watch == attr or watch == "*":
                    cbs.append(cb)
        for cb in cbs:
            cb(self, attr, value)

    def _save(self, attr, value):
        # TODO only care if it changes?
        self._arlo.st.set(self._to_storage_key(attr), value)

    def _save_and_do_callbacks(self, attr, value):
        self._save(attr, value)
        self._do_callbacks(attr, value)

    def _load(self, attr, default=None):
        return self._arlo.st.get(self._to_storage_key(attr), default)

    def _load_matching(self, attr, default=None):
        return self._arlo.st.get_matching(self._to_storage_key(attr), default)

    def update_resources(self, props):
        for key in RESOURCE_KEYS + RESOURCE_UPDATE_KEYS:
            value = props.get(key, None)
            if value is not None:
                self._save_and_do_callbacks(key, value)

    @property
    def storage_id(self):
        return self._storage_id

    @property
    def name(self):
        """Returns the device name."""
        return self._name

    @property
    def model_id(self):
        """Returns the model id."""
        return self._attrs.get("modelId", None)

    def attribute(self, attr, default=None):
        """Return the value of attribute attr.

        PyArlo stores its state in key/value pairs. This returns the value associated with the key.

        See PyArlo for a non-exhaustive list of attributes.

        :param attr: Attribute to look up.
        :type attr: str
        :param default: value to return if not found.
        :return: The value associated with attribute or `default` if not found.
        """
        value = self._load(attr, None)
        if value is None:
            value = self._attrs.get(attr, None)
        if value is None:
            value = self._attrs.get("properties", {}).get(attr, None)
        if value is None:
            value = default
        return value

    def add_attr_callback(self, attr, cb):
        """Add an callback to be triggered when an attribute changes.

        Used to register callbacks to track device activity. For example, get a notification whenever
        motion stop and starts.

        See PyArlo for a non-exhaustive list of attributes.

        :param attr: Attribute - eg `motionStarted` - to monitor.
        :type attr: str
        :param cb: Callback to run.
        """
        with self._lock:
            self._attr_cbs_.append((attr, cb))
