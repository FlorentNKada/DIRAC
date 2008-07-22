import os
from DIRAC import S_OK, S_ERROR
from DIRAC.Core.Security.X509Chain import X509Chain
from DIRAC.Core.Security.VOMS import VOMS
from DIRAC.Core.Security import Locations, CS

def getProxyInfo( proxyLoc = False, showUsername = False ):

  if not proxyLoc:
    proxyLoc = Locations.getProxyLocation()

  if not proxyLoc:
    return S_ERROR( "Can't find valid proxy" )

  chain = X509Chain()
  retVal = chain.loadProxyFromFile( proxyLoc )
  if not retVal[ 'OK' ]:
    return S_ERROR( "Can't load %s: %s" % ( proxyLoc, retVal[ 'Message' ] ) )

  info = chain.getInfoAsString()['Value']
  info += "\npath        : %s\n" % proxyLoc
  if showUsername:
    retVal = chain.getIssuerCert()
    if not retVal[ 'OK' ]:
      dn = ""
    else:
      dn = retVal[ 'Value' ].getSubjectDN()[ 'Value' ]
    retVal = CS.getUsernameForDN( dn )
    if not retVal[ 'OK' ]:
      info += "username    : <unknown>\n"
    else:
      info += "username    : %s\n" % retVal[ 'Value' ]
  if chain.isVOMS()['Value']:
    info += "extra       : Contains voms extensions\n"
    voms = VOMS()
    retVal = voms.getVOMSAttributes( proxyLoc )
    if retVal[ 'OK' ]:
      for entry in retVal[ 'Value' ]:
        info += " voms data  : %s\n" % entry
    else:
      info += " Can't decode voms data (%s)\n" % retVal[ 'Message' ]
  return S_OK( info )

def Proxy( proxyLoc = False ):


  if not proxyLoc:
    proxyLoc = Locations.getProxyLocation()
  result = S_OK(proxyLoc)

  if not proxyLoc:
    return S_ERROR( "Can't find valid proxy" )

  chain = X509Chain()
  retVal = chain.loadProxyFromFile( proxyLoc )
  if not retVal[ 'OK' ]:
    return S_ERROR( "Can't load %s: %s" % ( proxyLoc, retVal[ 'Message' ] ) )

  retVal = chain.isValidProxy()
  if not retVal[ 'OK' ]:
    return retVal

  result['Chain'] = chain

  retVal = chain.getIssuerCert()
  if not retVal[ 'OK' ]:
    return S_ERROR( "Can't get DN: %s" % retVal[ 'Message' ] )
  else:
    result['OwnerDN'] = retVal[ 'Value' ].getSubjectDN()[ 'Value' ]

  retVal = chain.getDIRACGroup()
  if not retVal[ 'OK' ]:
    return S_ERROR( "Can't get DN: %s" % retVal[ 'Message' ] )
  else:
    result['Group'] = retVal[ 'Value' ]
  
  result['isVOMS'] = chain.isVOMS()['Value']

  if result['isVOMS']:
    voms = VOMS()
    retVal = voms.getVOMSAttributes( proxyLoc )
    if retVal[ 'OK' ]:
      result['VOMSAttributes'] = retVal[ 'Value' ]
    else:
      return S_ERROR( "Can't decode voms data: %s" % retVal[ 'Message' ] )

  retVal = CS.getUsernameForDN( result['OwnerDN'] )
  if not retVal[ 'OK' ]:
    result['Owner'] = 'unknown'
  else:
    result['Owner'] = retVal[ 'Value' ]

  return result
  