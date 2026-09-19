package com.gitgalaxy.modernized.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import lombok.RequiredArgsConstructor;
import com.gitgalaxy.modernized.service.Cbact02cService;

import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.MediaType;

@RestController
@RequestMapping("/api/v1/cbact02c")
@RequiredArgsConstructor
public class Cbact02cController {

    private final Cbact02cService cbact02cService;

    @PostMapping(value = "/execute-batch", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> executeCbact02cBatch(
        @RequestParam("cardfileFile") MultipartFile cardfileFile
    ) {
        // BATCH PARADIGM DETECTED
        // Pass the InputStream directly to the Service layer.
        cbact02cService.executeCbact02c(/* pass streams here */);

        return ResponseEntity.noContent().build();
    }
}