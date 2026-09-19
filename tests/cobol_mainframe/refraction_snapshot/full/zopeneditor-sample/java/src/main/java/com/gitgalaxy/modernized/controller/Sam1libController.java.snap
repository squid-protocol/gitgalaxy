package com.gitgalaxy.modernized.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import lombok.RequiredArgsConstructor;
import com.gitgalaxy.modernized.service.Sam1libService;

import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.MediaType;

@RestController
@RequestMapping("/api/v1/sam1lib")
@RequiredArgsConstructor
public class Sam1libController {

    private final Sam1libService sam1libService;

    @PostMapping(value = "/execute-batch", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> executeSam1libBatch(
        @RequestParam("custfileFile") MultipartFile custfileFile,
        @RequestParam("custoutFile") MultipartFile custoutFile,
        @RequestParam("tranfileFile") MultipartFile tranfileFile,
        @RequestParam("custrptFile") MultipartFile custrptFile
    ) {
        // BATCH PARADIGM DETECTED
        // Pass the InputStream directly to the Service layer.
        sam1libService.executeSam1lib(/* pass streams here */);

        // Expected Outputs: CUSTOUT, CUSTRPT
        return ResponseEntity.ok().build();
    }
}