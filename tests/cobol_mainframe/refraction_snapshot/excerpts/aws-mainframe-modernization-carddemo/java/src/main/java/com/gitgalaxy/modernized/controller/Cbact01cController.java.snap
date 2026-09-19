package com.gitgalaxy.modernized.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import lombok.RequiredArgsConstructor;
import com.gitgalaxy.modernized.service.Cbact01cService;

import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.MediaType;

@RestController
@RequestMapping("/api/v1/cbact01c")
@RequiredArgsConstructor
public class Cbact01cController {

    private final Cbact01cService cbact01cService;

    @PostMapping(value = "/execute-batch", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> executeCbact01cBatch(
        @RequestParam("acctfileFile") MultipartFile acctfileFile,
        @RequestParam("outfileFile") MultipartFile outfileFile,
        @RequestParam("arryfileFile") MultipartFile arryfileFile,
        @RequestParam("vbrcfileFile") MultipartFile vbrcfileFile
    ) {
        // BATCH PARADIGM DETECTED
        // Pass the InputStream directly to the Service layer.
        cbact01cService.executeCbact01c(/* pass streams here */);

        // Expected Outputs: ARRYFILE, OUTFILE, VBRCFILE
        return ResponseEntity.ok().build();
    }
}