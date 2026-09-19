package com.gitgalaxy.modernized.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import lombok.RequiredArgsConstructor;
import com.gitgalaxy.modernized.service.CobolSam1Service;

import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.MediaType;

@RestController
@RequestMapping("/api/v1/cobol-sam1")
@RequiredArgsConstructor
public class CobolSam1Controller {

    private final CobolSam1Service cobolSam1Service;

    @PostMapping(value = "/execute-batch", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> executeCobolSam1Batch(
        @RequestParam("custfileFile") MultipartFile custfileFile,
        @RequestParam("custoutFile") MultipartFile custoutFile,
        @RequestParam("tranfileFile") MultipartFile tranfileFile,
        @RequestParam("custrptFile") MultipartFile custrptFile
    ) {
        // BATCH PARADIGM DETECTED
        // Pass the InputStream directly to the Service layer.
        cobolSam1Service.executeCobolSam1(/* pass streams here */);

        // Expected Outputs: CUSTOUT, CUSTRPT
        return ResponseEntity.ok().build();
    }
}