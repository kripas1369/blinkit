# SPHEREx Data Flow (Block B1)


    A[1. User: RA, Dec] --> B[2. coords.py: Parse ICRS & MJD-AVG]
    
    B --> C[3. config.py: QR3/DR1 Active Releases]
   
    C --> D[4. archive.py: TAP Search & SIA2 S3 Key]
   
    D --> E[5. flags.py: Defect Masking keep SOURCE bit 21]
   
    E --> F[6. archive.py: Group Visits gap > 30d, span <= 60d]
   
    F --> G[7. Block B2: S3 Range Stream & Coadd]

Pipeline Steps:

1. Coordinates ("coords.py"): Normalizes user input into ICRS degrees and observation MJD-AVG

2. Collections ("config.py"):** Targets active science releases ("spherex_dr1", "spherex_qr3"); QR2 is retired.

3. Archive Search ("archive.py")Queries IRSA TAP for footprints covering coordinates (1-hour cache).


4. AWS S3 Keys ("archive.py")Fallback to IRSA SIA2 to extract public S3 keys when obscore is blank.


5.Quality Flags ("flags.py")Bitmasks hardware defects ("HOT", "COLD", "GHOST") while keeping "SOURCE` (bit 21) unmasked.

6.Visits ("archive.py"):Clusters exposures into observation epochs

