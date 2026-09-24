package com.gitgalaxy.modernized.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import lombok.RequiredArgsConstructor;
import com.gitgalaxy.modernized.service.R001bydlService;

import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.MediaType;

@RestController
@RequestMapping("/api/v1/r001bydl")
@RequiredArgsConstructor
public class R001bydlController {

    private final R001bydlService r001bydlService;

    @PostMapping(value = "/execute-batch", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> executeR001bydlBatch(
        @RequestParam("regFile") MultipartFile regFile,
        @RequestParam("nyregFile") MultipartFile nyregFile
    ) {
        // BATCH PARADIGM DETECTED
        // Pass the InputStream directly to the Service layer.
        r001bydlService.executeR001bydl(/* pass streams here */);

        // Expected Outputs: NYREG
        return ResponseEntity.ok().build();
    }
}