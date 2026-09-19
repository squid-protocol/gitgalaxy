package com.gitgalaxy.modernized.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import lombok.RequiredArgsConstructor;
import com.gitgalaxy.modernized.service.MultirootSamSam1Service;

import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.MediaType;

@RestController
@RequestMapping("/api/v1/multiroot-sam-sam1")
@RequiredArgsConstructor
public class MultirootSamSam1Controller {

    private final MultirootSamSam1Service multirootSamSam1Service;

    @PostMapping(value = "/execute-batch", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> executeMultirootSamSam1Batch(
        @RequestParam("custfileFile") MultipartFile custfileFile,
        @RequestParam("custoutFile") MultipartFile custoutFile,
        @RequestParam("tranfileFile") MultipartFile tranfileFile,
        @RequestParam("custrptFile") MultipartFile custrptFile
    ) {
        // BATCH PARADIGM DETECTED
        // Pass the InputStream directly to the Service layer.
        multirootSamSam1Service.executeMultirootSamSam1(/* pass streams here */);

        // Expected Outputs: CUSTOUT, CUSTRPT
        return ResponseEntity.ok().build();
    }
}