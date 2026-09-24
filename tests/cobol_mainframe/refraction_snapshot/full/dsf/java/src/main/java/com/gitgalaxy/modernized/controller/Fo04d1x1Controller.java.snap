package com.gitgalaxy.modernized.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import lombok.RequiredArgsConstructor;
import com.gitgalaxy.modernized.service.Fo04d1x1Service;

import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.MediaType;

@RestController
@RequestMapping("/api/v1/fo04d1x1")
@RequiredArgsConstructor
public class Fo04d1x1Controller {

    private final Fo04d1x1Service fo04d1x1Service;

    @PostMapping(value = "/execute-batch", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> executeFo04d1x1Batch(
        @RequestParam("sys004File") MultipartFile sys004File,
        @RequestParam("sys005File") MultipartFile sys005File,
        @RequestParam("sys006File") MultipartFile sys006File
    ) {
        // BATCH PARADIGM DETECTED
        // Pass the InputStream directly to the Service layer.
        fo04d1x1Service.executeFo04d1x1(/* pass streams here */);

        // Expected Outputs: SYS005
        return ResponseEntity.ok().build();
    }
}