package com.gitgalaxy.modernized.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import lombok.RequiredArgsConstructor;
import com.gitgalaxy.modernized.service.CbimportService;

import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.MediaType;

@RestController
@RequestMapping("/api/v1/cbimport")
@RequiredArgsConstructor
public class CbimportController {

    private final CbimportService cbimportService;

    @PostMapping(value = "/execute-batch", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> executeCbimportBatch(
        @RequestParam("expfileFile") MultipartFile expfileFile,
        @RequestParam("custoutFile") MultipartFile custoutFile,
        @RequestParam("acctoutFile") MultipartFile acctoutFile,
        @RequestParam("xrefoutFile") MultipartFile xrefoutFile,
        @RequestParam("trnxoutFile") MultipartFile trnxoutFile,
        @RequestParam("cardoutFile") MultipartFile cardoutFile,
        @RequestParam("erroutFile") MultipartFile erroutFile
    ) {
        // BATCH PARADIGM DETECTED
        // Pass the InputStream directly to the Service layer.
        cbimportService.executeCbimport(/* pass streams here */);

        // Expected Outputs: ACCTOUT, CARDOUT, CUSTOUT, ERROUT, TRNXOUT, XREFOUT
        return ResponseEntity.ok().build();
    }
}