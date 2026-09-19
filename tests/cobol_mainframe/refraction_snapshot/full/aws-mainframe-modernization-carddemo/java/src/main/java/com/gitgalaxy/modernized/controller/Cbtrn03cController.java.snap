package com.gitgalaxy.modernized.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import lombok.RequiredArgsConstructor;
import com.gitgalaxy.modernized.service.Cbtrn03cService;

import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.MediaType;

@RestController
@RequestMapping("/api/v1/cbtrn03c")
@RequiredArgsConstructor
public class Cbtrn03cController {

    private final Cbtrn03cService cbtrn03cService;

    @PostMapping(value = "/execute-batch", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> executeCbtrn03cBatch(
        @RequestParam("tranfileFile") MultipartFile tranfileFile,
        @RequestParam("cardxrefFile") MultipartFile cardxrefFile,
        @RequestParam("trantypeFile") MultipartFile trantypeFile,
        @RequestParam("trancatgFile") MultipartFile trancatgFile,
        @RequestParam("tranreptFile") MultipartFile tranreptFile,
        @RequestParam("dateparmFile") MultipartFile dateparmFile
    ) {
        // BATCH PARADIGM DETECTED
        // Pass the InputStream directly to the Service layer.
        cbtrn03cService.executeCbtrn03c(/* pass streams here */);

        // Expected Outputs: TRANREPT
        return ResponseEntity.ok().build();
    }
}