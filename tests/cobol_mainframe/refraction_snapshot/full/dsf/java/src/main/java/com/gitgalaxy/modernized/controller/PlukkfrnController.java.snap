package com.gitgalaxy.modernized.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import lombok.RequiredArgsConstructor;
import com.gitgalaxy.modernized.service.PlukkfrnService;

import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.MediaType;

@RestController
@RequestMapping("/api/v1/plukkfrn")
@RequiredArgsConstructor
public class PlukkfrnController {

    private final PlukkfrnService plukkfrnService;

    @PostMapping(value = "/execute-batch", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> executePlukkfrnBatch(
        @RequestParam("sysinFile") MultipartFile sysinFile,
        @RequestParam("outputFile") MultipartFile outputFile,
        @RequestParam("inputFile") MultipartFile inputFile,
        @RequestParam("sysut1File") MultipartFile sysut1File
    ) {
        // BATCH PARADIGM DETECTED
        // Pass the InputStream directly to the Service layer.
        plukkfrnService.executePlukkfrn(/* pass streams here */);

        // Expected Outputs: OUTPUT, SYSUT1
        return ResponseEntity.ok().build();
    }
}