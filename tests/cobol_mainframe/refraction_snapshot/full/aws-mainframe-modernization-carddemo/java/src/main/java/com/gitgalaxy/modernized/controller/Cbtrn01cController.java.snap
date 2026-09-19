package com.gitgalaxy.modernized.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import lombok.RequiredArgsConstructor;
import com.gitgalaxy.modernized.service.Cbtrn01cService;

import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.MediaType;

@RestController
@RequestMapping("/api/v1/cbtrn01c")
@RequiredArgsConstructor
public class Cbtrn01cController {

    private final Cbtrn01cService cbtrn01cService;

    @PostMapping(value = "/execute-batch", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> executeCbtrn01cBatch(
        @RequestParam("dalytranFile") MultipartFile dalytranFile,
        @RequestParam("custfileFile") MultipartFile custfileFile,
        @RequestParam("xreffileFile") MultipartFile xreffileFile,
        @RequestParam("cardfileFile") MultipartFile cardfileFile,
        @RequestParam("acctfileFile") MultipartFile acctfileFile,
        @RequestParam("tranfileFile") MultipartFile tranfileFile
    ) {
        // BATCH PARADIGM DETECTED
        // Pass the InputStream directly to the Service layer.
        cbtrn01cService.executeCbtrn01c(/* pass streams here */);

        return ResponseEntity.noContent().build();
    }
}