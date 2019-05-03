
import pprint
import threading

from . import storage
from .constant import ( BATTERY_KEY,
                                CONNECTION_KEY,
                                PARENT_ID_KEY,
                                PRIVACY_KEY,
                                RESOURCE_KEYS,
                                RESOURCE_UPDATE_KEYS,
                                SIGNAL_STR_KEY,
                                UNIQUE_ID_KEY,
                                XCLOUD_ID_KEY )

class ArloDevice(object):

    def __init__( self,name,arlo,attrs ):
        self._name = name
        self._arlo = arlo
        self._attrs = attrs

        self._lock = threading.Lock()
        self._attr_cbs_ = []

        # stuff we use a lot
        self._device_id   = attrs.get('deviceId',None)
        self._device_type = attrs.get('deviceType',None)
        self._unique_id   = attrs.get('uniqueId',None)

        # add a listener
        self._arlo._be.add_listener( self,self._event_handler )

    def __repr__(self):
        # Representation string of object.
        return "<{0}:{1}:{2}>".format(self.__class__.__name__,self._device_type,self._name)

    def _event_handler( self,resource,event ):
        self._arlo.debug( self.name + ' DEVICE got one ' + resource )

    def _do_callbacks( self,attr,value ):
        cbs = []
        with self._lock:
            for watch,cb in self._attr_cbs_:
                if watch == attr or watch == '*':
                    cbs.append( cb )
        for cb in cbs:
            cb( self,attr,value )

    def _save_and_do_callbacks( self,attr,value ):
        key = [ self.device_id,attr ]
        old_value = self._arlo._st.get( key,None )
        # enable this to only callback on updates
        #if not old_value or old_value != value:
        #output = 'updating ' + attr + ' for ' + self.device_id + ' to ' + str(value)
        #self._arlo.debug( output[:90] )
        self._arlo._st.set( key,value )
        self._do_callbacks( attr,value )

    @property
    def name(self):
        return self._name

    @property
    def device_id(self):
        return self._device_id

    @property
    def resource_id(self):
        return self._device_id

    @property
    def serial_number(self):
        return self._device_id

    @property
    def device_type(self):
        return self._device_type

    @property
    def model_id(self):
        return self._attrs.get('modelId',None)

    @property
    def hw_version(self):
        return self._attrs.get('properties',{}).get('hwVersion',None)

    @property
    def timezone(self):
        return self._attrs.get('properties',{}).get('olsonTimeZone',None)

    @property
    def user_id(self):
        return self._attrs.get('userId',None)

    @property
    def user_role(self):
        return self._attrs.get('userRole',None)

    @property
    def xcloud_id(self):
        return self._arlo._st.get( [self._device_id,XCLOUD_ID_KEY],'UNKNOWN' )
 
    @property
    def web_id(self):
        return self.user_id + '_web'

    @property
    def unique_id(self):
        return self._unique_id

    def attribute( self,attr,default=None ):
        value = self._arlo._st.get( [self._device_id,attr],None )
        if value is None:
            value = self._attrs.get(attr,None)
        if value is None:
            value = self._attrs.get('properties',{}).get(attr,None)
        if value is None:
            value = default
        return value

    def add_attr_callback( self,attr,cb ):
        with self._lock:
            self._attr_cbs_.append( (attr,cb) )

    def has_capability( self,cap ):
        return False

    @property
    def state( self ):
        return 'idle'


class ArloChildDevice(ArloDevice):

    def __init__( self,name,arlo,attrs ):
        super().__init__( name,arlo,attrs )

    def _event_handler( self,resource,event ):
        self._arlo.debug( self.name + ' got ' + resource )

        # this as generated by a 'devices' request to the base station
        if resource == 'cameras' or resource == 'doorbells':
            self._arlo.debug( 'base info' )
            for key in RESOURCE_KEYS:
                value = event.get(key,None)
                if value is not None:
                    self._save_and_do_callbacks( key,value )
            return

        # this is sent by the actual device, normally as a response to something
        if resource.startswith('cameras/') or resource.startswith('doorbells/'):
            self._arlo.debug( 'device info' )
            props = event.get('properties',{})
            for key in RESOURCE_UPDATE_KEYS:
                value = props.get( key,None )
                if value is not None:
                    self._save_and_do_callbacks( key,value )
            return

    @property
    def parent_id(self):
        return self._arlo._st.get( [self._device_id,PARENT_ID_KEY],'UNKNOWN' )

    @property
    def base_station(self):
        for base in self._arlo.base_stations:
            if base.device_id == self.parent_id:
                return base
        # some cameras don't have base stations... it's its own basestation...
        return self

    @property
    def battery_level(self):
        return self._arlo._st.get( [self._device_id,BATTERY_KEY],100 )

    @property
    def signal_strength(self):
        return self._arlo._st.get( [self._device_id,SIGNAL_STR_KEY],3 )

    def has_capability( self,cap ):
        if cap in ( 'motionDetected' ):
            return True
        return False

    @property
    def too_cold( self ):
        return self._arlo._st.get( [self._device_id,CONNECTION_KEY],'unknown' ) == 'thermalShutdownCold'

    @property
    def is_on( self ):
        return not self._arlo._st.get( [self._device_id,PRIVACY_KEY],False )

    def turn_on( self ):
        self._arlo._bg.run( self._arlo._be.async_on_off,base=self.base_station,device=self,privacy_on=False )

    def turn_off( self ):
        self._arlo._bg.run( self._arlo._be.async_on_off,base=self.base_station,device=self,privacy_on=True )

    @property
    def state( self ):
        if not self.is_on:
            return 'turned off'
        if self.too_cold:
            return 'offline, too cold'
        return 'idle'

