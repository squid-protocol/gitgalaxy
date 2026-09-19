package com.gitgalaxy.modernized.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import lombok.RequiredArgsConstructor;
import com.gitgalaxy.modernized.service.CobtupdtService;

import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.MediaType;

@RestController
@RequestMapping("/api/v1/cobtupdt")
@RequiredArgsConstructor
public class CobtupdtController {

    private final CobtupdtService cobtupdtService;

    @PostMapping(value = "/execute-batch", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> executeCobtupdtBatch(
        @RequestParam("inpfileFile") MultipartFile inpfileFile
    ) {
        // BATCH PARADIGM DETECTED
        // Pass the InputStream directly to the Service layer.
        cobtupdtService.executeCobtupdt(/* pass streams here */);

        return ResponseEntity.noContent().build();
    }
}