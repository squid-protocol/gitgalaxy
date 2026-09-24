package com.gitgalaxy.modernized.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import lombok.RequiredArgsConstructor;
import com.gitgalaxy.modernized.service.FrmerkService;

import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.MediaType;

@RestController
@RequestMapping("/api/v1/frmerk")
@RequiredArgsConstructor
public class FrmerkController {

    private final FrmerkService frmerkService;

    @PostMapping(value = "/execute-batch", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> executeFrmerkBatch(
        @RequestParam("inputFile") MultipartFile inputFile,
        @RequestParam("outputFile") MultipartFile outputFile,
        @RequestParam("paramFile") MultipartFile paramFile
    ) {
        // BATCH PARADIGM DETECTED
        // Pass the InputStream directly to the Service layer.
        frmerkService.executeFrmerk(/* pass streams here */);

        // Expected Outputs: OUTPUT
        return ResponseEntity.ok().build();
    }
}