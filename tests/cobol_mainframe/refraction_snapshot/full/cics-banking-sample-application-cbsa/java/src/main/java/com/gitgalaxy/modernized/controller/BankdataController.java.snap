package com.gitgalaxy.modernized.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import lombok.RequiredArgsConstructor;
import com.gitgalaxy.modernized.service.BankdataService;

import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.MediaType;

@RestController
@RequestMapping("/api/v1/bankdata")
@RequiredArgsConstructor
public class BankdataController {

    private final BankdataService bankdataService;

    @PostMapping(value = "/execute-batch", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> executeBankdataBatch(
        @RequestParam("vsamFile") MultipartFile vsamFile
    ) {
        // BATCH PARADIGM DETECTED
        // Pass the InputStream directly to the Service layer.
        bankdataService.executeBankdata(/* pass streams here */);

        // Expected Outputs: VSAM
        return ResponseEntity.ok().build();
    }
}