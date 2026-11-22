   DEFINE ALTERNATEINDEX (NAME(AWS.M2.CARDDEMO.TRANSACT.VSAM.AIX)-
   RELATE(AWS.M2.CARDDEMO.TRANSACT.VSAM.KSDS)                    -
   KEYS(26 304)                                                  -
   NONUNIQUEKEY                                                  -
   UPGRADE                                                       -
   RECORDSIZE(4400,4400)                                         -
   VOLUMES(AWSHJ1)                                               -
   CYLINDERS(5,1))                                               -
   DATA (NAME(AWS.M2.CARDDEMO.TRANSACT.VSAM.AIX.DATA))           -
   INDEX (NAME(AWS.M2.CARDDEMO.TRANSACT.VSAM.AIX.INDEX))
   DEFINE PATH                                           -
   (NAME(AWS.M2.CARDDEMO.TRANSACT.VSAM.AIX.PATH)        -
    PATHENTRY(AWS.M2.CARDDEMO.TRANSACT.VSAM.AIX))
   BLDINDEX                                                      -
   INDATASET(AWS.M2.CARDDEMO.TRANSACT.VSAM.KSDS)                 -
   OUTDATASET(AWS.M2.CARDDEMO.TRANSACT.VSAM.AIX)
