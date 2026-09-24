       IDENTIFICATION DIVISION.                                                 
       PROGRAM-ID. LISTMRK.                                                     
       DATE-WRITTEN.26/9/85.                                                    
       AUTHOR. CURTIS FLEKKE.                                                   
       ENVIRONMENT DIVISION.                                                    
       CONFIGURATION SECTION.                                                   
       SPECIAL-NAMES.                                                           
           C01 IS PAGE1.                                                        
       INPUT-OUTPUT SECTION.                                                    
       FILE-CONTROL.                                                            
           SELECT INPUTA ASSIGN TO UT-S-INPUT.                                  
             SELECT UTFIL ASSIGN TO UT-S-OUTPUT.                                
             SELECT INFIL ASSIGN TO UT-S-PARAM.                                 
       DATA DIVISION.                                                           
       FILE SECTION.                                                            
       FD  INFIL                                                                
           LABEL RECORD IS OMITTED                                              
               BLOCK CONTAINS 0 RECORDS.                                        
       01  INN-AAR   PIC X(80).                                                 
       FD  INPUTA                                                               
           LABEL RECORD IS OMITTED                                              
               BLOCK CONTAINS 0 RECORDS.                                        
       01  INN-FR.                                                              
        02 TRKNR     PIC 9(4).                                                  
        02 FILLER    PIC X(11).                                                 
        02 NAVN      PIC X(26).                                                 
        02 GATE1     PIC X(25).                                                 
        02 GATE2     PIC X(25).                                                 
        02 POSTSTED  PIC X(21).                                                 
                                                                                
       FD  UTFIL                                                                
           LABEL RECORD IS OMITTED                                              
               BLOCK CONTAINS 0 RECORDS.                                        
       01  UTPOSTEN    PIC  X(133).                                             
       WORKING-STORAGE SECTION.                                                 
                                                                                
       01  TELLER       PIC 9(2).                                               
                                                                                
       01  OMR-DATA1.                                                           
        02 FILLER    PIC X(7) VALUE SPACES.                                     
        02 NAVN1     PIC X(33).                                                 
       01  OMR-DATA2.                                                           
        02 FILLER    PIC X(7) VALUE SPACES.                                     
        02 NAVN2     PIC X(33).                                                 
       01  OMR-DATA22.                                                          
        02 FILLER    PIC X(7) VALUE SPACES.                                     
        02 NAVN22    PIC X(33).                                                 
       01  OMR-DATA3.                                                           
        02 FILLER    PIC X(7) VALUE SPACES.                                     
        02 NAVN3     PIC X(33).                                                 
                                                                                
       01  TRK-OVERSK1.                                                         
        02 FILLER        PIC X(5).                                              
        02 TRKNR-L       PIC 9(4).                                              
        02 FILLER        PIC X(5).                                              
        02 LOVERSK       PIC X(15) VALUE 'FYLLER 67 ÅR I '.                     
        02 AARSTALL      PIC X(4).                                              
        02 FILLER        PIC X(12).                                             
                                                                                
       01  PARAMIN.                                                             
        02 INNAAR         PIC X(4).                                             
        02 FILLER        PIC X(76).                                             
                                                                                
       01  BLK PIC X(133) VALUE SPACES.                                         
       PROCEDURE DIVISION.                                                      
       STARTEN.                                                                 
           OPEN INPUT INPUTA INFIL                                              
                OUTPUT UTFIL.                                                   
           MOVE ZERO TO TRKNR-L.                                                
           MOVE ZERO TO TELLER.                                                 
           READ INFIL.                                                          
           MOVE INN-AAR TO PARAMIN.                                             
           MOVE INNAAR TO AARSTALL.                                             
       TEST-DATA.                                                               
           READ INPUTA AT END GO TO SLUTT.                                      
           IF TRKNR = TRKNR-L GO TO DANN-DATA.                                  
           GO TO DANN-NYSIDE.                                                   
       DANN-DATA.                                                               
           MOVE NAVN TO NAVN1.                                                  
           MOVE GATE1 TO NAVN2.                                                 
           MOVE GATE2 TO NAVN22.                                                
           MOVE POSTSTED TO NAVN3.                                              
       SKRIV-SIDE.                                                              
           WRITE UTPOSTEN FROM BLK.                                             
           WRITE UTPOSTEN FROM OMR-DATA1.                                       
           WRITE UTPOSTEN FROM OMR-DATA2.                                       
           WRITE UTPOSTEN FROM OMR-DATA22.                                      
           WRITE UTPOSTEN FROM OMR-DATA3.                                       
           WRITE UTPOSTEN FROM BLK.                                             
           GO TO TEST-DATA.                                                     
       DANN-NYSIDE.                                                             
           MOVE TRKNR TO TRKNR-L.                                               
           WRITE UTPOSTEN FROM BLK AFTER ADVANCING PAGE1.                       
           WRITE UTPOSTEN FROM TRK-OVERSK1.                                     
           WRITE UTPOSTEN FROM TRK-OVERSK1.                                     
           WRITE UTPOSTEN FROM BLK.                                             
           WRITE UTPOSTEN FROM TRK-OVERSK1.                                     
           WRITE UTPOSTEN FROM BLK.                                             
           GO TO DANN-DATA.                                                     
       SLUTT.                                                                   
           CLOSE INPUTA UTFIL.                                                  
           STOP RUN.                                                            
                                                                                
