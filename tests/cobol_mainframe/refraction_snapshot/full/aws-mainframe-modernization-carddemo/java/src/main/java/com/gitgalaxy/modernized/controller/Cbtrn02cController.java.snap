package com.gitgalaxy.modernized.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import lombok.RequiredArgsConstructor;
import com.gitgalaxy.modernized.service.Cbtrn02cService;

import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.MediaType;

@RestController
@RequestMapping("/api/v1/cbtrn02c")
@RequiredArgsConstructor
public class Cbtrn02cController {

    private final Cbtrn02cService cbtrn02cService;

    @PostMapping(value = "/execute-batch", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> executeCbtrn02cBatch(
        @RequestParam("dalytranFile") MultipartFile dalytranFile,
        @RequestParam("tranfileFile") MultipartFile tranfileFile,
        @RequestParam("xreffileFile") MultipartFile xreffileFile,
        @RequestParam("dalyrejsFile") MultipartFile dalyrejsFile,
        @RequestParam("acctfileFile") MultipartFile acctfileFile,
        @RequestParam("tcatbalfFile") MultipartFile tcatbalfFile
    ) {
        // BATCH PARADIGM DETECTED
        // Pass the InputStream directly to the Service layer.
        cbtrn02cService.executeCbtrn02c(/* pass streams here */);

        // Expected Outputs: ACCTFILE, DALYREJS, TCATBALF, TRANFILE
        return ResponseEntity.ok().build();
    }
}