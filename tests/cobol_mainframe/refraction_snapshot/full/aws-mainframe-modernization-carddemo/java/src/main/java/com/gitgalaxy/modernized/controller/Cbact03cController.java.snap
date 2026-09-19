package com.gitgalaxy.modernized.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import lombok.RequiredArgsConstructor;
import com.gitgalaxy.modernized.service.Cbact03cService;

import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.MediaType;

@RestController
@RequestMapping("/api/v1/cbact03c")
@RequiredArgsConstructor
public class Cbact03cController {

    private final Cbact03cService cbact03cService;

    @PostMapping(value = "/execute-batch", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> executeCbact03cBatch(
        @RequestParam("xreffileFile") MultipartFile xreffileFile
    ) {
        // BATCH PARADIGM DETECTED
        // Pass the InputStream directly to the Service layer.
        cbact03cService.executeCbact03c(/* pass streams here */);

        return ResponseEntity.noContent().build();
    }
}