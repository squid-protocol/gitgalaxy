package com.gitgalaxy.modernized.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import lombok.RequiredArgsConstructor;
import com.gitgalaxy.modernized.service.CbexportService;

import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.MediaType;

@RestController
@RequestMapping("/api/v1/cbexport")
@RequiredArgsConstructor
public class CbexportController {

    private final CbexportService cbexportService;

    @PostMapping(value = "/execute-batch", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> executeCbexportBatch(
        @RequestParam("custfileFile") MultipartFile custfileFile,
        @RequestParam("acctfileFile") MultipartFile acctfileFile,
        @RequestParam("xreffileFile") MultipartFile xreffileFile,
        @RequestParam("transactFile") MultipartFile transactFile,
        @RequestParam("cardfileFile") MultipartFile cardfileFile,
        @RequestParam("expfileFile") MultipartFile expfileFile
    ) {
        // BATCH PARADIGM DETECTED
        // Pass the InputStream directly to the Service layer.
        cbexportService.executeCbexport(/* pass streams here */);

        // Expected Outputs: EXPFILE
        return ResponseEntity.ok().build();
    }
}