package com.gitgalaxy.modernized.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import lombok.RequiredArgsConstructor;
import com.gitgalaxy.modernized.service.Cbact04cService;

import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.MediaType;

@RestController
@RequestMapping("/api/v1/cbact04c")
@RequiredArgsConstructor
public class Cbact04cController {

    private final Cbact04cService cbact04cService;

    @PostMapping(value = "/execute-batch", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> executeCbact04cBatch(
        @RequestParam("tcatbalfFile") MultipartFile tcatbalfFile,
        @RequestParam("xreffileFile") MultipartFile xreffileFile,
        @RequestParam("acctfileFile") MultipartFile acctfileFile,
        @RequestParam("discgrpFile") MultipartFile discgrpFile,
        @RequestParam("transactFile") MultipartFile transactFile
    ) {
        // BATCH PARADIGM DETECTED
        // Pass the InputStream directly to the Service layer.
        cbact04cService.executeCbact04c(/* pass streams here */);

        // Expected Outputs: ACCTFILE, TRANSACT
        return ResponseEntity.ok().build();
    }
}