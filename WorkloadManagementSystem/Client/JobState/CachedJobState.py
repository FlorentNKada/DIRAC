""" I wish who wrote this would have put some doc...
"""

import types
import copy
import time

from DIRAC.Core.Utilities import Time, DEncode
from DIRAC import S_OK, S_ERROR, gLogger
from DIRAC.WorkloadManagementSystem.Client.JobState.JobState import JobState
from DIRAC.WorkloadManagementSystem.Client.JobState.JobManifest import JobManifest

class CachedJobState( object ):

  log = gLogger.getSubLogger( "CachedJobState" )

  def __init__( self, jid, skipInitState = False ):
    self.dOnlyCache = False
    self.__jid = jid
    self.__jobState = JobState( jid )
    self.cleanState( skipInitState = skipInitState )

  def cleanState( self, skipInitState = False ):
    self.__cache = {}
    self.__jobLog = []
    self.__insertIntoTQ = False
    self.__dirtyKeys = set()
    self.__manifest = False
    self.__initState = None
    self.__lastValidState = time.time()
    if not skipInitState:
      result = self.getAttributes( [ "Status", "MinorStatus", "LastUpdateTime" ] )
      if result[ 'OK' ]:
        self.__initState = result[ 'Value' ]
      else:
        self.__initState = None

  def recheckValidity( self, graceTime = 600 ):
    now = time.time()
    if graceTime <= 0 or now - self.__lastValidState > graceTime:
      self.__lastValidState = now
      result = self.__jobState.getAttributes( [ "Status", "MinorStatus", "LastUpdateTime" ] )
      if not result[ 'OK' ]:
        return result
      currentState = result[ 'Value' ]
      if not currentState == self.__initState:
        return S_OK( False )
      return S_OK( True )
    return S_OK( self.valid )

  @property
  def valid( self ):
    return self.__initState != None

  @property
  def jid( self ):
    return self.__jid

  def getDirtyKeys( self ):
    return set( self.__dirtyKeys )

  def commitChanges( self ):
    if self.__initState == None:
      return S_ERROR( "CachedJobState( %d ) is not valid" % self.__jid )
    changes = {}
    for k in self.__dirtyKeys:
      changes[ k ] = self.__cache[ k ]
    result = self.__jobState.commitCache( self.__initState, changes, self.__jobLog )
    try:
      result.pop( 'rpcStub' )
    except KeyError:
      pass
    if not result[ 'OK' ]:
      self.cleanState()
      return result
    if not result[ 'Value' ]:
      self.cleanState()
      return S_ERROR( "Initial state was different" )
    newState = result[ 'Value' ]
    self.__jobLog = []
    self.__dirtyKeys.clear()
    #Save manifest
    if self.__manifest and self.__manifest.isDirty():
      result = self.__jobState.setManifest( self.__manifest )
      if not result[ 'OK' ]:
        self.cleanState()
        for _ in range( 5 ):
          if self.__jobState.rescheduleJob()[ 'OK' ]:
            break
        return result
      self.__manifest.clearDirty()
    #Insert into TQ
    if self.__insertIntoTQ:
      result = self.__jobState.insertIntoTQ()
      if not result[ 'OK' ]:
        self.cleanState()
        for _ in range( 5 ):
          if self.__jobState.rescheduleJob()[ 'OK' ]:
            break
        return result
      self.__insertIntoTQ = False

    self.__initState = newState
    self.__lastValidState = time.time()
    return S_OK()

  def serialize( self ):
    if self.__manifest:
      manifest = ( self.__manifest.dumpAsCFG(), self.__manifest.isDirty() )
    else:
      manifest = None
    return DEncode.encode( ( self.__jid, self.__cache, self.__jobLog, manifest,
                             self.__initState, self.__insertIntoTQ, tuple( self.__dirtyKeys ) ) )

  @staticmethod
  def deserialize( stub ):
    dataTuple = DEncode.decode( stub )
    if len( dataTuple ) != 7:
      return S_ERROR( "Invalid stub" )
    #jid
    if type( dataTuple[0] ) not in ( types.IntType, types.LongType ):
      return S_ERROR( "Invalid stub 0" )
    #cache
    if type( dataTuple[1] ) != types.DictType:
      return S_ERROR( "Invalid stub 1" )
    #trace
    if type( dataTuple[2] ) != types.ListType:
      return S_ERROR( "Invalid stub 2" )
    #manifest
    tdt3 = type( dataTuple[3] )
    if tdt3 != types.NoneType and ( tdt3 != types.TupleType and len( dataTuple[3] ) != 2 ):
      return S_ERROR( "Invalid stub 3" )
    #initstate
    if type( dataTuple[4] ) != types.DictType:
      return S_ERROR( "Invalid stub 4" )
    #Insert into TQ
    if type( dataTuple[5] ) != types.BooleanType:
      return S_ERROR( "Invalid stub 5" )
    #Dirty Keys
    if type( dataTuple[6] ) != types.TupleType:
      return S_ERROR( "Invalid stub 6" )
    cjs = CachedJobState( dataTuple[0], skipInitState = True )
    cjs.__cache = dataTuple[1]
    cjs.__jobLog = dataTuple[2]
    dt3 = dataTuple[3]
    if dataTuple[3]:
      manifest = JobManifest()
      result = manifest.loadCFG( dt3[0] )
      if not result[ 'OK' ]:
        return result
      if dt3[1]:
        manifest.setDirty()
      else:
        manifest.clearDirty()
      cjs.__manifest = manifest
    cjs.__initState = dataTuple[4]
    cjs.__insertIntoTQ = dataTuple[5]
    cjs.__dirtyKeys = set( dataTuple[6] )
    return S_OK( cjs )

  def __cacheAdd( self, key, value ):
    self.__cache[ key ] = value
    self.__dirtyKeys.add( key )

  def __cacheExists( self, keyList ):
    if type( keyList ) in types.StringTypes:
      keyList = [ keyList ]
    for key in keyList:
      if key not in self.__cache:
        return False
    return True

  def __cacheResult( self, cKey, functor, fArgs = None ):
    keyType = type( cKey )
    #If it's a string
    if keyType in types.StringTypes:
      if cKey not in self.__cache:
        if self.dOnlyCache:
          return S_ERROR( "%s is not cached" )
        if not fArgs:
          fArgs = tuple()
        result = functor( *fArgs )
        if not result[ 'OK' ]:
          return result
        data = result[ 'Value' ]
        self.__cache[ cKey ] = data
      return S_OK( self.__cache[ cKey ] )
    #Tuple/List
    elif keyType in ( types.ListType, types.TupleType ):
      if not self.__cacheExists( cKey ):
        if self.dOnlyCache:
          return S_ERROR( "%s is not cached" )
        if not fArgs:
          fArgs = tuple()
        result = functor( *fArgs )
        if not result[ 'OK' ]:
          return result
        data = result[ 'Value' ]
        if len( cKey ) != len( data ):
          gLogger.warn( "CachedJobState.__memorize( %s, %s = %s ) doesn't receive the same amount of values as keys" % ( cKey,
                                                                                                           functor, data ) )
          return data
        for i in range( len( cKey ) ):
          self.__cache[ cKey[ i ] ] = data[i]
      #Prepare result
      return S_OK( tuple( [ self.__cache[ cK ]  for cK in cKey ] ) )
    else:
      raise RuntimeError( "Cache key %s does not have a valid type" % cKey )

  def __cacheDict( self, prefix, functor, keyList = None ):
    if not keyList or not self.__cacheExists( [ "%s.%s" % ( prefix, key ) for key in keyList ] ):
      result = functor( keyList )
      if not result[ 'OK' ]:
        return result
      data = result [ 'Value' ]
      for key in data:
        cKey = "%s.%s" % ( prefix, key )
        #If the key is already in the cache. DO NOT TOUCH. User may have already modified it.
        #We update the coming data with the cached data
        if cKey in self.__cache:
          data[ key ] = self.__cache[ cKey ]
        else:
          self.__cache[ cKey ] = data[ key ]
      return S_OK( data )
    return S_OK( dict( [ ( key, self.__cache[ "%s.%s" % ( prefix, key ) ] ) for key in keyList ] ) )

  def _inspectCache( self ):
    return copy.deepcopy( self.__cache )

  def _clearCache( self ):
    self.__cache = {}

  @property
  def _internals( self ):
    if self.__manifest:
      manifest = ( self.__manifest.dumpAsCFG(), self.__manifest.isDirty() )
    else:
      manifest = None
    return ( self.__jid, self.dOnlyCache, dict( self.__cache ),
             list( self.__jobLog ), manifest, dict( self.__initState ), list( self.__dirtyKeys ) )

#
# Manifest
#

  def getManifest( self ):
    if not self.__manifest:
      result = self.__jobState.getManifest()
      if not result[ 'OK' ]:
        return result
      self.__manifest = result[ 'Value' ]
    return S_OK( self.__manifest )

  def setManifest( self, manifest ):
    if not isinstance( manifest, JobManifest ):
      jobManifest = JobManifest()
      result = jobManifest.load( str( manifest ) )
      if not result[ 'OK' ]:
        return result
      manifest = jobManifest
    manifest.setDirty()
    self.__manifest = manifest
    # self.__manifest.clearDirty()
    return S_OK()

# Attributes
#

  def __addLogRecord( self, majorStatus = None, minorStatus = None, appStatus = None, source = None ):
    record = {}
    if majorStatus:
      record[ 'status' ] = majorStatus
    if minorStatus:
      record[ 'minor' ] = minorStatus
    if appStatus:
      record[ 'application' ] = appStatus
    if not record:
      return
    if not source:
      source = "Unknown"
    self.__jobLog.append( ( record, Time.dateTime(), source ) )

  def setStatus( self, majorStatus, minorStatus = None, appStatus = None, source = None ):
    self.__cacheAdd( 'att.Status', majorStatus )
    if minorStatus:
      self.__cacheAdd( 'att.MinorStatus', minorStatus )
    if appStatus:
      self.__cacheAdd( 'att.ApplicationStatus', appStatus )
    self.__addLogRecord( majorStatus, minorStatus, appStatus, source )
    return S_OK()

  def setMinorStatus( self, minorStatus, source = None ):
    self.__cacheAdd( 'att.MinorStatus', minorStatus )
    self.__addLogRecord( minorStatus = minorStatus, source = source )
    return S_OK()

  def getStatus( self ):
    return self.__cacheResult( ( 'att.Status', 'att.MinorStatus' ), self.__jobState.getStatus )

  def setAppStatus( self, appStatus, source = None ):
    self.__cacheAdd( 'att.ApplicationStatus', appStatus )
    self.__addLogRecord( appStatus = appStatus, source = source )
    return S_OK()

  def getAppStatus( self ):
    return self.__cacheResult( 'att.ApplicationStatus', self.__jobState.getAppStatus )
#
# Attribs
#

  def setAttribute( self, name, value ):
    if type( name ) not in types.StringTypes:
      return S_ERROR( "Attribute name has to be a string" )
    self.__cacheAdd( "att.%s" % name, value )
    return S_OK()

  def setAttributes( self, attDict ):
    if type( attDict ) != types.DictType:
      return S_ERROR( "Attributes has to be a dictionary and it's %s" % str( type( attDict ) ) )
    for key in attDict:
      self.__cacheAdd( "att.%s" % key, attDict[ key ] )
    return S_OK()

  def getAttribute( self, name ):
    return self.__cacheResult( 'att.%s' % name, self.__jobState.getAttribute, ( name, ) )

  def getAttributes( self, nameList = None ):
    return self.__cacheDict( 'att', self.__jobState.getAttributes, nameList )

#Job params

  def setParameter( self, name, value ):
    if type( name ) not in types.StringTypes:
      return S_ERROR( "Job parameter name has to be a string" )
    self.__cacheAdd( 'jobp.%s' % name, value )
    return S_OK()

  def setParameters( self, pDict ):
    if type( pDict ) != types.DictType:
      return S_ERROR( "Job parameters has to be a dictionary" )
    for key in pDict:
      self.__cacheAdd( 'jobp.%s' % key, pDict[ key ] )
    return S_OK()

  def getParameter( self, name ):
    return self.__cacheResult( "jobp.%s" % name, self.__jobState.getParameter, ( name, ) )

  def getParameters( self, nameList = None ):
    return self.__cacheDict( 'jobp', self.__jobState.getParameters, nameList )

#Optimizer params

  def setOptParameter( self, name, value ):
    if type( name ) not in types.StringTypes:
      return S_ERROR( "Optimizer parameter name has to be a string" )
    self.__cacheAdd( 'optp.%s' % name, value )
    return S_OK()

  def setOptParameters( self, pDict ):
    if type( pDict ) != types.DictType:
      return S_ERROR( "Optimizer parameters has to be a dictionary" )
    for key in pDict:
      self.__cacheAdd( 'optp.%s' % key, pDict[ key ] )
    return S_OK()

  def getOptParameter( self, name ):
    return self.__cacheResult( "optp.%s" % name, self.__jobState.getOptParameter, ( name, ) )

  def getOptParameters( self, nameList = None ):
    return self.__cacheDict( 'optp', self.__jobState.getOptParameters, nameList )

#Other

  def resetJob( self, source = "" ):
    """ Reset the job!
    """
    return self.__jobState.resetJob( source = source )

  def getInputData( self ):
    return self.__cacheResult( "inputData" , self.__jobState.getInputData )

  def insertIntoTQ( self ):
    if self.valid:
      self.__insertIntoTQ = True
      return S_OK()
    return S_ERROR( "Cached state is invalid" )
