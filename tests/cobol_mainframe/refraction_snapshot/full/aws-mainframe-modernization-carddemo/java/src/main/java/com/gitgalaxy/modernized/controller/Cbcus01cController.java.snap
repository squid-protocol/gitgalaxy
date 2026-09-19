package com.gitgalaxy.modernized.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import lombok.RequiredArgsConstructor;
import com.gitgalaxy.modernized.service.Cbcus01cService;

import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.MediaType;

@RestController
@RequestMapping("/api/v1/cbcus01c")
@RequiredArgsConstructor
public class Cbcus01cController {

    private final Cbcus01cService cbcus01cService;

    @PostMapping(value = "/execute-batch", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> executeCbcus01cBatch(
        @RequestParam("custfileFile") MultipartFile custfileFile
    ) {
        // BATCH PARADIGM DETECTED
        // Pass the InputStream directly to the Service layer.
        cbcus01cService.executeCbcus01c(/* pass streams here */);

        return ResponseEntity.noContent().build();
    }
}